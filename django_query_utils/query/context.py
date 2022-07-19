from __future__ import annotations

import typing as t
from contextlib import contextmanager
from dataclasses import dataclass

from django.db import connections, DEFAULT_DB_ALIAS

from . import base, materializers

__all__ = "Query", "query_context"

try:
    from psycopg2 import sql
    RawQueryT = t.Union[str, sql.Composable]
except ImportError:
    RawQueryT = str  # type: ignore


@dataclass
class Query(t.Generic[base.ResultT]):
    query: RawQueryT
    arguments: t.Union[t.Mapping[str, t.Any], t.Collection[t.Any]] = ()
    materializer: materializers.ResultMaterializer[base.ResultT] = materializers.DictMaterializer()  # type: ignore

    def as_type(self, type_: t.Type[base.NewResultT]) -> Query[base.NewResultT]:
        return Query(self.query, self.arguments, self.materializer.to_type(type_))


@contextmanager
def query_context(*args, using=DEFAULT_DB_ALIAS, **kwargs):
    with connections[using].cursor(*args, **kwargs) as c:
        yield _MaterializedExecutionContext(c)


class BaseExecutionContext:
    __slots__ = "cursor",

    def __init__(self, cursor):
        self.cursor = cursor


class _MaterializedExecutionContext(BaseExecutionContext):
    __slots__ = ()

    def execute(self, query: Query[base.ResultT]) -> t.Iterable[base.ResultT]:
        self.cursor.execute(query.query, query.arguments)
        return query.materializer(self.cursor)
