from __future__ import annotations

import abc
import itertools
import typing as t

from . import base


class ResultMaterializer(t.Generic[base.ResultT], abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def __call__(self, cursor) -> t.Iterable[base.ResultT]:
        pass

    def to_type(self, type_: t.Type[base.NewResultT]) -> ResultMaterializer[base.NewResultT]:
        raise NotImplementedError


class SealedMaterializer(ResultMaterializer[base.ResultT], abc.ABC):
    __slots__ = ()

    def to_type(self, type_):
        raise base.SealedTransformError("Sealed materializer can't be transformed")


class PlainMaterializer(ResultMaterializer[t.Tuple[t.Any, ...]]):
    __slots__ = ()

    def __call__(self, cursor):
        return iter(cursor)

    def to_type(self, type_: t.Type[base.VargResultT]) -> SealedMaterializer[base.VargResultT]:
        return OneStarAdaptor(type_)


class FlatMaterializer(ResultMaterializer[t.Any]):
    __slots__ = ()

    def __call__(self, cursor):
        return (row[0] for row in cursor)

    def to_type(self, type_: t.Type[base.FlatResultT]) -> ResultMaterializer[base.FlatResultT]:
        return FlatAdaptor(type_)


class DictMaterializer(ResultMaterializer[t.Mapping[str, t.Any]]):
    __slots__ = ()

    def __call__(self, cursor):
        columns = tuple(col.name for col in cursor.description)
        return (dict((col, row) for col in columns) for row in cursor)

    def to_type(self, type_: t.Type[base.KwargResultT]) -> SealedMaterializer[base.KwargResultT]:
        return TwoStarAdaptor(type_)


class TypeMixin(t.Generic[base.ResultT]):
    __slots__ = ("type",)

    def __init__(self, type_: t.Type[base.ResultT]):
        self.type: t.Type[base.ResultT] = type_


class FlatAdaptor(SealedMaterializer[base.FlatResultT], TypeMixin[base.FlatResultT]):
    __slots__ = ()

    def __call__(self, cursor):
        return map(self.type, cursor)


class OneStarAdaptor(SealedMaterializer[base.VargResultT], TypeMixin[base.VargResultT]):
    __slots__ = ()

    def __call__(self, cursor):
        return itertools.starmap(self.type, iter(cursor))


class TwoStarAdaptor(SealedMaterializer[base.KwargResultT], TypeMixin[base.KwargResultT], DictMaterializer):
    __slots__ = ()

    def __call__(self, cursor):
        tp = self.type
        return (tp(**row) for row in super().__call__(cursor))


__all__ = (
    "ResultMaterializer",
    "SealedMaterializer",
    "PlainMaterializer",
    "DictMaterializer",
    "FlatMaterializer",
)
