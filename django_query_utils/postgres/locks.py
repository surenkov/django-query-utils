import contextlib
import enum
import hashlib
import typing as t

from django.apps import apps
from django.db import models, transaction, connection, OperationalError, InternalError

from psycopg2 import sql

__all__ = (
    "table_lock",
    "advisory_lock",
    "LockMode",
    "LockNowaitError",
    "LockTimeoutError",
)


class LockMode(str, enum.Enum):
    AccessShare = "ACCESS SHARE"
    RowShare = "ROW SHARE"
    RowExclusive = "ROW EXCLUSIVE"
    ShareUpdateExclusive = "SHARE UPDATE EXCLUSIVE"
    Share = "SHARE"
    ShareRowExclusive = "SHARE ROW EXCLUSIVE"
    Exclusive = "EXCLUSIVE"
    AccessExclusive = "ACCESS EXCLUSIVE"


class LockTimeoutError(OperationalError):
    """ Issued when lock timeout has been reached """


class LockNowaitError(LockTimeoutError):
    """ Issued while trying to lock already locked table with nowait set to True"""


class TableLock(contextlib.ContextDecorator):
    def __init__(self, *tables: str, using: str = None, mode: LockMode = None, nowait: bool = False, timeout: int = None):
        if nowait and timeout:
            raise ValueError("Can't set both nowait and timeout options")

        if timeout == 0:
            timeout, nowait = None, True  # type: ignore
        elif timeout is not None and timeout <= 0:
            raise ValueError("Lock timeout should be a positive integer")

        self.tables = tables
        self.using = using
        self.mode = mode
        self.nowait = nowait
        self.timeout = timeout

    @classmethod
    def for_model(cls, *models: t.Union[str, t.Type[models.Model]], **kwargs):
        all_models = (apps.get_model(_) if isinstance(_, str) else _ for _ in models)
        tables = (model._meta.db_table for model in all_models)
        return cls(*tables, **kwargs)

    def __enter__(self):
        query, params = self._prepare_lock_query()
        self._exec_lock_query(query, params)

    def __exit__(self, *exc_info):
        return False

    def _exec_lock_query(self, lock_query: sql.SQL, params: tuple[t.Any, ...]):
        conn = transaction.get_connection(self.using)
        with conn.cursor() as c:
            try:
                c.execute(lock_query, params)
            except OperationalError as e:
                if self.nowait:
                    raise LockNowaitError from e
                if self.timeout is not None:
                    raise LockTimeoutError(self.timeout) from e
                raise

    def _prepare_lock_query(self):
        empty, params, mode = sql.SQL(""), (), self.mode
        query = "LOCK TABLE {tables} {lock_mode} {nowait}"

        query = sql.SQL(query).format(
            tables=sql.SQL(", ").join(map(sql.Identifier, self.tables)),
            lock_mode=(empty if mode is None else sql.SQL(f"IN {mode.value} MODE")),
            nowait=(sql.SQL("NOWAIT") if self.nowait else empty),
        )

        if self.timeout is not None:
            query = sql.SQL("SET LOCAL lock_timeout = %s; {}").format(query)
            params = (f"{self.timeout}s",)

        return query, params


class AdvisoryLock(contextlib.ContextDecorator):
    _transaction: bool = False
    _connection = connection

    def __init__(self, *lock_id: t.Union[int, str], using: str = None, shared: bool = False, nowait: bool = False, timeout: int = None):
        if nowait and timeout:
            raise ValueError("Can't set both nowait and timeout options")
        if timeout == 0:
            timeout, nowait = None, True  # type: ignore
        elif timeout is not None and timeout < 0:
            raise ValueError("Timeout should be a positive integer")

        self.lock_id = self._validate_lock_id(lock_id)
        self.using = using
        self.shared = shared
        self.nowait = nowait
        self.timeout = timeout

    def __enter__(self):
        self._connection = conn = transaction.get_connection(self.using)
        self._transaction = conn.in_atomic_block
        if self.timeout is not None and not self._transaction:
            raise InternalError("Timeout can only be used in transaction block")

        lock_func = self._prepare_lock_function()
        with conn.cursor() as c:
            lock_func.exec(c)

    def __exit__(self, *exc_info):
        if (unlock_func := self._prepare_unlock_function()) is not None:
            with self._connection.cursor() as c:
                unlock_func.exec(c)

        self._connection = connection
        self._transaction = False
        return False

    def _prepare_lock_function(self) -> "_AdvisoryLockFunction":
        expr = sql.SQL("pg_")
        ctor, args = _AdvisoryLockFunction, {}

        if self.nowait:
            ctor = _NowaitAdvisoryLockFuncion
            expr += sql.SQL("try_")
        elif self.timeout is not None:
            ctor = _TimeoutAdvisoryLockFunction
            args["timeout"] = self.timeout

        expr += sql.SQL("advisory_xact_lock" if self._transaction else "advisory_lock")
        if self.shared:
            expr += sql.SQL("_shared")

        return ctor(expr, self.lock_id, **args)

    def _prepare_unlock_function(self) -> t.Optional["_AdvisoryLockFunction"]:
        if self._transaction:
            return None

        expr = sql.SQL("pg_advisory_unlock")
        if self.shared:
            expr += sql.SQL("_shared")

        return _AdvisoryLockFunction(expr, self.lock_id)

    def _validate_lock_id(self, lock_id) -> t.Union[tuple[int], tuple[int, int]]:
        """ Since ``pg_advisory_lock`` functions family expects either a single bigint
            or a pair of ints, application-specific IDs consisting of strings
            or large ints should be transformed either by clamping or hashing.
            I think the latter approach is better in a sense of avoiding collisions.
        """

        def prep_id_part(id_val: t.Union[int, str, bytes], bit_len: t.Literal[32, 64]):
            if isinstance(id_val, (str, t.ByteString)):
                if isinstance(id_val, str):
                    id_val = id_val.encode()

                digest = hashlib.md5(id_val, usedforsecurity=False).digest()
                id_hash = int.from_bytes(digest, "little", signed=True)
            elif isinstance(id_val, int):
                id_hash = id_val
            else:
                raise ValueError(f"Can't prepare lock id from {id_val}")

            # Reduce hash length to conform pg_advisory_lock signature
            # (64 OR (32, 32) bit signed int)

            hash_len = id_hash.bit_length()
            while hash_len > bit_len:
                hash_len >>= 1
                hi_mask = (1 << hash_len) - 1

                lo_mask = hi_mask << hash_len
                id_hash = (id_hash & hi_mask) ^ ((id_hash & lo_mask) >> hash_len)

            # Convert back to signed int
            signed_len = bit_len - 1
            return (id_hash & ((1 << signed_len) - 1)) - (id_hash & (1 << signed_len))

        if len(lock_id) == 1:
            valid_lock_id = (prep_id_part(lock_id[0], 64),)
        elif len(lock_id) == 2:
            a, b = lock_id
            valid_lock_id = prep_id_part(a, 32), prep_id_part(b, 32)
        else:
            raise ValueError(f"Unsupported number of arguments: {lock_id}")

        return valid_lock_id


class _AdvisoryLockFunction:
    __slots__ = "func", "lock_id"

    def __init__(
        self,
        func: sql.Composable,
        lock_id: t.Union[tuple[int], tuple[int, int]],
        *args,
        **kwargs,
    ):
        self.func = func
        self.lock_id = lock_id

    def get_lock_expr(self):
        expr_params = sql.SQL(", ").join((sql.Placeholder(),) * len(self.lock_id))
        expr = self.func + sql.SQL("({})").format(expr_params)
        return sql.SQL("SELECT {}").format(expr)

    def exec(self, cursor):
        cursor.execute(self.get_lock_expr(), self.lock_id)


class _NowaitAdvisoryLockFuncion(_AdvisoryLockFunction):
    __slots__ = ()

    def exec(self, cursor):
        cursor.execute(self.get_lock_expr(), self.lock_id)

        if not cursor.fetchone()[0]:
            raise LockNowaitError(self.lock_id)


class _TimeoutAdvisoryLockFunction(_AdvisoryLockFunction):
    __slots__ = "timeout"

    def __init__(
        self,
        func: sql.Composable,
        lock_id: t.Union[tuple[int], tuple[int, int]],
        timeout: int,
        *args,
        **kwargs,
    ):
        super().__init__(func, lock_id, *args, **kwargs)
        self.timeout = timeout

    def exec(self, cursor):
        cursor.execute("SET LOCAL lock_timeout = %s", [f"{self.timeout}s"])
        try:
            cursor.execute(self.get_lock_expr(), self.lock_id)
        except OperationalError as e:
            raise LockTimeoutError(self.lock_id, self.timeout) from e


table_lock = TableLock
advisory_lock = AdvisoryLock
