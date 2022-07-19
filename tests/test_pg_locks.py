import pytest
from threading import Thread

from django.apps import apps
from django.db import transaction, InternalError

from django_query_utils.postgres.locks import table_lock, advisory_lock, LockNowaitError, LockTimeoutError


@pytest.mark.django_db
def test_table_lock(reraise):
    def raise_nowait_err():
        with reraise, pytest.raises(LockNowaitError):
            with transaction.atomic(), table_lock("auth_user", nowait=True):
                assert False, "Should not reach there"

    with transaction.atomic(), table_lock("auth_user"):
        thread = Thread(target=raise_nowait_err)
        thread.start()
        thread.join(timeout=3)


@pytest.mark.django_db
def test_model_table_lock(reraise):
    User = apps.get_model("auth", "User")

    def raise_nowait_err():
        with reraise, pytest.raises(LockNowaitError):
            with transaction.atomic(), table_lock.for_model(User, "auth.Group", nowait=True):
                assert False, "Should not reach there"

    with transaction.atomic(), table_lock.for_model(User, "auth.Group"):
        thread = Thread(target=raise_nowait_err)
        thread.start()
        thread.join(timeout=3)


@pytest.mark.django_db
def test_table_lock_timeout(reraise):
    with pytest.raises(ValueError):
        table_lock("asdf", nowait=True, timeout=10)
        table_lock("asdf", timeout=-1)

    def raise_flight_lock_timeout_err():
        with reraise, pytest.raises(LockTimeoutError):
            with transaction.atomic(), table_lock("auth_user", timeout=1):
                assert False, "Should not reach there"

    def raise_flight_lock_nowait_err():
        with reraise, pytest.raises(LockNowaitError):
            with transaction.atomic(), table_lock("auth_user", timeout=0):
                assert False, "Should not reach there"

    with transaction.atomic(), table_lock("auth_user"):
        threads = []

        for func in [raise_flight_lock_timeout_err, raise_flight_lock_nowait_err]:
            thread = Thread(target=func)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join(timeout=3)


@pytest.mark.django_db
def test_advisory_lock(reraise):
    def raise_nowait_err():
        with reraise, pytest.raises(LockNowaitError), advisory_lock(1, nowait=True):
            assert False, "Should not reach there"

    def lock_passes():
        with reraise, advisory_lock(2, nowait=True):
            pass

    with advisory_lock(1):
        thread = Thread(target=raise_nowait_err)
        another = Thread(target=lock_passes)

        thread.start()
        another.start()

        thread.join(timeout=3)
        another.join(timeout=3)


@pytest.mark.django_db
def test_advisory_lock_timeout(reraise):
    with pytest.raises(ValueError):
        advisory_lock("asdf", 1, nowait=True, timeout=10)
        advisory_lock("asdf", 1, timeout=-1)

    def raise_timeout_err():
        with reraise, pytest.raises(LockTimeoutError):
            with transaction.atomic(), advisory_lock("asdf", 1, timeout=1):
                assert False, "Should not reach here"

    def raise_nowait_err():
        with reraise, pytest.raises(LockNowaitError):
            with transaction.atomic(), advisory_lock("asdf", 1, timeout=0):
                assert False, "Should not reach here"

    def raise_internal_err():
        with reraise, pytest.raises(InternalError):
            with advisory_lock("asdf", 2, timeout=1):
                assert False, "Should not be run outside of transaction"

    with advisory_lock("asdf", 1):
        threads = []

        for func in [raise_timeout_err, raise_nowait_err, raise_internal_err]:
            thread = Thread(target=func)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join(timeout=3)


@pytest.mark.parametrize(["lock_id"], [
    [(1 << 63 - 1,)],
    [(1 << 63,)],
    [(1 << 64,)],
    [(1 << 65,)],
    [(1 << 31 - 1, 1 << 31)],
    [(1 << 32, 1 << 33)],
])
@pytest.mark.django_db
def test_large_lock_ids(lock_id):
    with advisory_lock(*lock_id):
        pass
