from django.contrib.postgres.search import SearchQuery

from .lexer import WebSearchLexer
from .nodes import *


class WebSearchParser:
    def __init__(self, query: str, prefix_literal: bool = False):
        self.lexer = WebSearchLexer(query)
        self.expression = Empty
        self.prefix_literal = prefix_literal

    def __call__(self, **kwargs):
        for token in self.lexer:
            self.expression = self.evaluate(token)

        reduced_query = str(self.expression)
        return SearchQuery(reduced_query, **kwargs)

    def evaluate(self, token):
        self.lexer.push_token(token)
        return Conjunction(self.expression, self.disjunction())

    def disjunction(self):
        reduced_left = self.conjunction()
        token = self.lexer.get_token()

        while token == Disjunction.TOKEN_PARSE:
            reduced_right = self.conjunction()
            reduced_left = Disjunction(reduced_left, reduced_right)
            token = self.lexer.get_token()

        if token:
            self.lexer.push_token(token)

        return reduced_left

    def conjunction(self):
        reduced_left = self.parens()
        token = self.lexer.get_token()

        while token == Conjunction.TOKEN_PARSE:
            reduced_right = self.parens()
            reduced_left = Conjunction(reduced_left, reduced_right)
            token = self.lexer.get_token()

        if token:
            self.lexer.push_token(token)

        return reduced_left

    def parens(self):
        token = self.lexer.get_token()

        if token == Parens.OPEN_TOKEN:
            expr = self.disjunction()
            token = self.lexer.get_token()

            if token == Parens.CLOSE_TOKEN:
                expr = Parens(expr)
            elif token:
                self.lexer.push_token(token)
        elif token:
            self.lexer.push_token(token)
            expr = self.negation()
        else:
            expr = Empty
        return expr

    def negation(self):
        token = self.lexer.get_token()

        if token == Negation.TOKEN_PARSE:
            expr = Negation(self.parens())
        elif token:
            self.lexer.push_token(token)
            expr = self.literal()
        else:
            expr = Empty

        return expr

    def literal(self):
        expr = Literal(self.lexer.get_token())
        if self.prefix_literal and not expr.exact_match:
            expr = Prefix(expr)
        return expr
