import pytest

from dataclasses import dataclass
from psycopg2 import sql

from django_query_utils import Query, query_context, PlainMaterializer

@pytest.fixture
def sample_users(db, django_user_model):
    User = django_user_model

    return User.objects.bulk_create([
        User(first_name="John", last_name="Doe", username="jdoe"),
        User(first_name="Jane", last_name="Doe", username="jadoe"),
        User(first_name="Mike", last_name="Wazowski", username="mwazowski"),
    ])


@pytest.mark.django_db
def test_query_helper(sample_users):
    query = Query("select first_name, last_name from auth_user where username = %(uname)s", {"uname": "jdoe"})

    with query_context(using="default") as c:
        results = list(c.execute(query))

    assert results == [{"first_name": "John", "last_name": "Doe"}]


@pytest.mark.django_db
def test_query_helper_with_plain_materializer(sample_users):
    query = Query(
        "select first_name, last_name from auth_user where username = %s",
        ["jdoe"],
        materializer=PlainMaterializer(),
    )

    with query_context(using="default") as c:
        results = list(c.execute(query))

    assert results == [("John", "Doe")]


@pytest.mark.django_db
def test_query_helper_to_class_transformer(sample_users):
    query = Query("select first_name, last_name from auth_user where username = %(uname)s", {"uname": "jdoe"})

    @dataclass
    class MyUser:
        first_name: str
        last_name: str

    with query_context() as c:
        results = c.execute(query.as_type(MyUser))
        assert list(results) == [MyUser(first_name="John", last_name="Doe")]


def test_query_helper_with_psycopg_sql(sample_users):
    raw_q = sql.SQL("select first_name, last_name from auth_user where username = {}")
    query = Query(raw_q.format(sql.Literal("jdoe")))

    with query_context() as c:
        results = list(c.execute(query))

    assert results == [{"first_name": "John", "last_name": "Doe"}]
