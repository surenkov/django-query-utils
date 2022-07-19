import typing as t
from dataclasses import dataclass

ExprT = t.TypeVar("ExprT", bound=t.Union[str, "Node"])


class Node:
    __slots__ = ()
    PRIORITY: t.ClassVar[int]


@dataclass
class UnaryOp(t.Generic[ExprT], Node):
    __slots__ = "expr"
    expr: ExprT

    def __iter__(self):
        yield self.expr

    def __bool__(self):
        return bool(self.expr)

    def __str__(self):
        return str(self.expr)


@dataclass
class BinaryOp(t.Generic[ExprT], Node):
    __slots__ = "lhs", "rhs"
    TOKEN_PARSE = ""
    TOKEN_JOIN = ""

    lhs: ExprT
    rhs: ExprT

    def __iter__(self):
        return iter((self.lhs, self.rhs))

    def __bool__(self):
        return any(self)

    def __str__(self):
        inner_expr = filter(None, self)
        return self.TOKEN_JOIN.join(map(str, inner_expr))


class Disjunction(BinaryOp[Node]):
    __slots__ = ()
    TOKEN_PARSE = "|"
    TOKEN_JOIN = " | "
    PRIORITY = 1


class Conjunction(BinaryOp[Node]):
    __slots__ = ()
    TOKEN_PARSE = "&"
    TOKEN_JOIN = " & "
    PRIORITY = 3

    def __str__(self):
        return self.TOKEN_JOIN.join(self._expr_parts)

    @property
    def _expr_parts(self):
        for expr in self:
            if expr.PRIORITY < self.PRIORITY:
                expr = Parens(expr)
            if expr:
                yield str(expr)


class Parens(UnaryOp[Node]):
    __slots__ = ()
    OPEN_TOKEN, CLOSE_TOKEN = "(", ")"
    PRIORITY = 4

    def __str__(self):
        result = ""
        if (expr := self.expr):
            if isinstance(expr, Parens):
                expr = expr.expr
            result = "".join((self.OPEN_TOKEN, str(expr), self.CLOSE_TOKEN))
        return result


class Negation(UnaryOp[Node]):
    __slots__ = ()
    TOKEN_PARSE = "!"
    TOKEN_JOIN = "!"
    PRIORITY = 5

    def __str__(self):
        result = ""
        if (expr := self.expr):
            if expr.PRIORITY < Parens.PRIORITY:
                expr = Parens(expr)
            result = self.TOKEN_JOIN + str(expr)
        return result


@dataclass
class Literal(UnaryOp[str]):
    PRIORITY = 6
    OPEN_TOKEN, CLOSE_TOKEN = "'", "'"
    QUOTES = "'", '"'

    def __str__(self):
        return "".join((self.OPEN_TOKEN, self.sanitized_expr, self.CLOSE_TOKEN))

    def __bool__(self):
        return bool(self.sanitized_expr)

    @property
    def exact_match(self):
        expr = self.expr
        return expr.startswith(self.QUOTES) and expr.endswith(expr[0])

    @property
    def sanitized_expr(self):
        return self.expr.strip("'\"").replace("\\", "\\\\").replace("'", "\\'")


class Prefix(UnaryOp[Literal]):
    __slots__ = ()
    PRIORITY = 3
    PREFIX = ":*"

    def __str__(self):
        result = ""
        if (expr := self.expr):
            result = str(expr) + self.PREFIX
        return result


Empty = Literal("")
