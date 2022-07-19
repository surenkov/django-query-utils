import pytest
import django_filters

from django.db.models import Value as V
from django.contrib.postgres.search import SearchVector

from django_query_utils.postgres import filters
from .models import FTSModel


def make_sample_users(User):
    return User.objects.bulk_create([
        User(first_name="John", last_name="Doe", username="jdoe"),
        User(first_name="Jane", last_name="Doe", username="jadoe"),
        User(first_name="Mike", last_name="Wazowski", username="mwazowski"),
    ])

def make_sample_fts():
    return FTSModel.objects.bulk_create([
        FTSModel(search_vector=SearchVector(V("hello world"))),
        FTSModel(search_vector=SearchVector(V("foo bar"))),
        FTSModel(search_vector=SearchVector(V("baz test"))),
    ])


@pytest.mark.django_db
def test_full_text_search_filter(django_user_model):
    make_sample_users(django_user_model)

    class MyFilterSet(django_filters.FilterSet):
        search = filters.FullTextSearchFilter(
            vector=("first_name", "last_name"),
            search_type="custom",
        )

    qs = django_user_model.objects.all()
    filterset = MyFilterSet({"search": "(John | Mike | Dan) Doe"}, qs)

    assert list(filterset.qs) == list(qs.filter(first_name="John"))


@pytest.mark.django_db
def test_stored_full_text_search_filter():
    fts_instances = make_sample_fts()

    class MyFilterSet(django_filters.FilterSet):
        search = filters.StoredFullTextSearchFilter(
            field_name="search_vector",
            search_type="custom",
            prefix=True,
        )

    qs = FTSModel.objects.all()
    filterset = MyFilterSet({"search": "HELL | fo"}, qs)

    assert list(filterset.qs) == fts_instances[:2]
