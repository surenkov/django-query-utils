import abc
import typing as t

from django.contrib.postgres.search import SearchVector, SearchQuery

from django.db.models import F, QuerySet
from django.db.models.expressions import BaseExpression

from django_filters.constants import EMPTY_VALUES
from django_filters.filters import CharFilter

from .websearch import WebSearchParser

__all__ = "FullTextSearchFilter", "StoredFullTextSearchFilter"


class _FullTextSearchBase(CharFilter, abc.ABC):
    search_type: str = "plain"
    invert: bool = False
    prefix: bool = False
    config: t.Optional[str] = None

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs

        query = self.get_search_query(value)
        qs, search_field = self.get_search_field(qs)

        lookup = {search_field: query}
        return self.get_method(qs)(**lookup)

    def get_search_query(self, value) -> SearchQuery:
        query_args = dict(config=self.config, invert=self.invert)
        query_args["search_type"] = search_type = self.search_type

        if search_type == "custom":
            query = self._get_custom_search_query(value, **query_args)
        else:
            query = SearchQuery(value, **query_args)

        return query

    @abc.abstractmethod
    def get_search_field(self, qs: QuerySet) -> t.Tuple[QuerySet, str]:
        ...

    def _get_custom_search_query(self, query_str: str, **kwargs):
        kwargs.update(search_type="raw")
        parser = WebSearchParser(query_str, prefix_literal=self.prefix)
        return parser(**kwargs)


class FullTextSearchFilter(_FullTextSearchBase):
    """Django REST filter around ``django.contrib.postgres.search`` expressions.

    Accepts ``SearchVector`` instance, string or collection of expressions,
    ``search_type`` for ``SearchQuery`` and locale ``config``

    Example:
    >>> search = FullTextSearchFilter(
    >>>     vector=("field_1", "field__subfield"),  # or `SearchVector` instance
    >>>     search_type="phrase",
    >>>     config="french",
    >>> )
    """

    _InnerExpr = t.Union[str, BaseExpression]
    _VectorExpr = t.Union[_InnerExpr, t.Collection[_InnerExpr], SearchVector]

    def __init__(
        self,
        *args,
        vector: _VectorExpr,
        suffix: str = "search",
        prefix: bool = False,
        config: str = None,
        invert: bool = False,
        search_type: str = "plain",
        extra: dict = None,
        **kwargs,
    ):
        """
        :param vector: Either ``SearchVector``, string or collection of expressions.
        :param suffix: Appendix for query annotation, optional.
        :param search_type: ``SearchQuery``'s search type.
        :param config: Locale config for ``SearchVector``
        """
        super().__init__(*args, **kwargs)
        extra = extra or {}

        if callable(vector):
            vector = vector(config, **extra)
        if isinstance(vector, (str, BaseExpression)):
            vector = SearchVector(vector, config=config, **extra)
        elif not isinstance(vector, SearchVector):
            vector = SearchVector(*vector, config=config, **extra)

        self.vector = vector
        self.suffix = suffix
        self.config = config
        self.invert = invert
        self.search_type = search_type
        self.prefix = prefix

    def get_search_field(self, qs):
        field = f"{self.field_name}_{self.suffix}"
        vector_annotation = {field: self.vector}
        return qs.annotate(**vector_annotation), field


class StoredFullTextSearchFilter(_FullTextSearchBase):
    _VectorField = t.Union[str, F]

    def __init__(
        self,
        *args,
        invert: bool = False,
        config: str = None,
        prefix: bool = False,
        search_type: str = "plain",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.invert = invert
        self.config = config
        self.search_type = search_type
        self.prefix = prefix

    def get_search_field(self, qs):
        return qs, self.field_name
