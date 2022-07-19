import typing as t

ResultT = t.TypeVar("ResultT", covariant=True)
NewResultT = t.TypeVar("NewResultT")


class _FlatCtorProto(t.Protocol[ResultT]):
    def __init__(self, arg: ResultT):
        ...

class _VargCtorProto(t.Protocol):
    def __init__(self, *args):
        ...


class _KwargCtorProto(t.Protocol):
    def __init__(self, **kwargs):
        ...


VargResultT = t.TypeVar("VargResultT", bound=_VargCtorProto)
KwargResultT = t.TypeVar("KwargResultT", bound=_KwargCtorProto)
FlatResultT = t.TypeVar("FlatResultT", bound=_FlatCtorProto)


class SealedTransformError(Exception):
    __slots__ = ()
