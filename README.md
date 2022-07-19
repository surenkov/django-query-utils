![PyPI Version](https://img.shields.io/pypi/v/django-query-utils)

## PostgreSQL locks

Django already exposes row-level locks with `QuerySet.select_for_update()` method.
What's missing is table-level and advisory locks:

``` python
from django_query_utils.postgres.locks import table_lock, LockMode

with table_lock("auth_user", "auth_group", mode=LockMode.Exclusive, timeout=10):
    """ Perform some esclusive operations on locked tables """


# Set a lock for Django model tables

from django.contrib.auth import models

with table_lock.for_model(models.User, models.Group, **kwargs):
    ...
```

[Advisory locks support](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)

``` python
from django_query_utils.postgres.locks import advisory_lock

lock_id = 42

with advisory_lock(lock_id, using="default", nowait=True):
    """ Perform some actions with locked resources """


# Create a more meaningful lock.
# Postgres spports either a single `bigint` or (`int`, `int`) pair as a lock_id.
# `advisory_lock` tries to convert any strings (or bigger ints) to postgres format
# either with hashing and bit shifts.

from django.db import transaction
from django.contrib.auth.models import User

user = User.objects.get(id=42)

with transaction.atomic(), advisory_lock("user:act", user.id, timeout=10):
    """ Perform some actions with locked resources.
        Timeout is only awailable within a transaction block. """

```


## PostgreSQL full-text search support for `django-filter`

``` python
from django_query_utils.postgres.filters import FullTextSearchFilter


class MyFilterSet(django_filters.FilterSet):
    search = FullTextSearchFilter(
        vector=("field_1", "field__subfield"),  # or `SearchVector` instance
        search_type="phrase",
        config="french",
    )
```

With `search_type="custom"` you may pass custom query expressions

``` python

class MyFilterSet(django_filters.FilterSet):
    search = FullTextSearchFilter(
        vector=("first_name", "last_name", "email"),  # or `SearchVector` instance
        search_type="phrase",
    )


qs = User.objects.all()
filter = MyFilterSet({"searh": "(John | Mike | Dan) Doe"}, qs)
```



## Raw Query wrappers:

``` python
from django_query_utils import Query, query_context

query = Query("select first_name, last_name from auth_user where email = %(email)s", {"email": "jdoe@example.com"})

with query_context(using="default") as c:
    results = list(c.execute(query))

assert results == [{"first_name": "John", "last_name": "Doe"}]
```

Different result materializers:

``` python
from django_query_utils import Query, Dict query_context

query = Query(
    "select first_name, last_name from auth_user where email = %(email)s",
    {"email": "jdoe@example.com"},
    materializer=PlainMaterializer(),
)

with query_context(using="default") as c:
    results = list(c.execute(query))

assert results == [("John", "Doe")]

```

More sophisticated transformers to kwarg classes:

``` python
from dataclasses import dataclass


@dataclass
class MyUser:
    first_name: str
    last_name: str


with query_context() as c:
    results = c.execute(query.as_type(MyUser))
    assert list(results) == [MyUser(first_name="John", last_name="Doe")]
```

(PostgreSQL only) `psycopg2.sql` query formatting support:

``` python
from psycopg2 import sql

raw_q = sql.SQL("select first_name, last_name from auth_user where email = {}")
query = Query(raw_q.format(sql.Literal("jdoe@example.com")))

...
```
