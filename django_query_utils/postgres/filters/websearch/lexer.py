import typing as t
from shlex import shlex


class WebSearchLexer(t.Iterator[str]):
    NON_TERM = "!()&|"
    PAR_OPEN, PAR_CLOSE = "()"

    BIN_OP = "&|"
    CONS = "&"

    REDUCE_BIN_OPS = "&|)"
    POST_CONS_OP = "!(&|"
    PRE_CONS_OP = "&|)"

    def __init__(self, query: str):
        self._lex = shlex(query, posix=False)
        self._exp_level = 0

    def __iter__(self):
        return self

    def __next__(self):
        token = self._extract_token()
        token = self._concatenate_operations(token)
        token = self._reduce_binary_operations(token)

        if token is self._lex.eof and not (token := self._close_parentheses()):
            raise StopIteration

        return self._adjust_expression_level(token)

    def get_token(self) -> str:
        return next(self, "")

    def peek_token(self) -> str:
        token = self._extract_token()
        self._lex.push_token(token)
        return token

    def push_token(self, token: str):
        self._lex.push_token(token)

    def _extract_token(self) -> str:
        try:
            token = self._lex.get_token()
        except ValueError:
            self._recover_from_failure()
            token = self._extract_token()

        if token == self.PAR_CLOSE and self._exp_level <= 0:
            token = self._extract_token()

        return token

    def _recover_from_failure(self):
        missing_quote = self._lex.token[0]
        self._lex.push_source(missing_quote)

    def _concatenate_operations(self, token: str) -> str:
        if token and (next_token := self._extract_token()):
            self.push_token(next_token)

            if token not in self.POST_CONS_OP and next_token not in self.PRE_CONS_OP:
                self.push_token(self.CONS)

        return token

    def _reduce_binary_operations(self, token) -> str:
        if not token:
            return token

        if token in self.BIN_OP:
            next_token = self._extract_token()

            if next_token and next_token in self.REDUCE_BIN_OPS:
                token = self._reduce_binary_operations(next_token)
            elif next_token:
                self.push_token(next_token)

        elif token in self.POST_CONS_OP:
            next_token = self._extract_token()

            if next_token and next_token in self.BIN_OP:
                token = self._reduce_binary_operations(token)
            elif next_token:
                self.push_token(next_token)

        return token

    def _adjust_expression_level(self, token) -> str:
        if token == self.PAR_OPEN:
            self._exp_level += 1
        elif token == self.PAR_CLOSE:
            self._exp_level -= 1

        return token

    def _close_parentheses(self) -> str:
        if self._exp_level > 0:
            return self.PAR_CLOSE
        return self._lex.eof
