from typing import List, Tuple
from copy import deepcopy
from enum import Enum


class TokenTypes(Enum):
    MAIN = -2
    QUOTATION_MARK = -1
    SKIP = 0
    OP = 1
    NEWLINE = 2
    ENDMARKER = 3
    MISMATCH = 4
    STRING = 5
    NAME = 6
    DOT = 7
    NUMBER = 8
    COMMENT = 9
    TUPLE = 10  # <expression>, <expression>
    PARENTHESIS = 11  # (<expression>)
    SQUARE_BRACKETS = 12  # [<expression>]
    CURLY_BRACES = 13  # {<expression>}


class TokenType:
    type: TokenTypes

    def __init__(self, t: TokenTypes):
        self.type = t

    def __eq__(self, other):
        if isinstance(other, TokenTypes):
            return self.type == other

        return self.type == other.type

    def __ne__(self, other):
        if isinstance(other, TokenTypes):
            return self.type != other

        return self.type != other.type

    def __str__(self):
        return f'TokenType(type={self.type.value} ({self.type.name}))'

    __repr__ = __str__


class DummyToken:
    type: TokenTypes
    value: str | List['Token'] | List[List['Token']]

    def __init__(self, t: TokenTypes | None, value: str | List['Token'] | List[List['Token']]):
        self.type = t
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, TokenType | DummyToken | Token):
            return self.value == other

        if isinstance(other, TokenType):
            return self.type == other.type

        if self.type is None:
            return self.value == other.value

        return self.type == other.type and self.value == other.value

    def __ne__(self, other):
        if not isinstance(other, TokenType | DummyToken | Token):
            return self.value != other

        if isinstance(other, TokenType):
            return self.type != other.type

        if self.type is None:
            return self.value != other.value

        return self.type != other.type or self.value != other.value

    def __str__(self):
        return f'DummyToken(type={self.type.value} ({self.type.name}), value={repr(self.value)})'

    __repr__ = __str__

    def copy(self):
        return deepcopy(self)


class Token:
    type: TokenTypes
    value: str | List['Token'] | List[List['Token']]
    start: Tuple[int, int, int]
    end: Tuple[int, int]
    line: str

    def __init__(
            self,
            t: TokenTypes,
            value: str | List['Token'] | List[List['Token']],
            start: Tuple[int, int, int],
            end: Tuple[int, int],
            line: str
    ):
        self.type = t
        self.value = value
        self.start = start
        self.end = end
        self.line = line

    def __eq__(self, other):
        if isinstance(other, tuple | list):
            for o in other:
                if self != o:
                    return False

            return True

        if not isinstance(other, TokenType | DummyToken | Token):
            return self.value == other

        if isinstance(other, TokenType):
            return self.type == other.type

        return self.type == other.type and self.value == other.value

    def __ne__(self, other):
        if isinstance(other, tuple | list):
            for o in other:
                if self == o:
                    return False

            return True

        if not isinstance(other, TokenType | DummyToken | Token):
            return self.value != other

        if isinstance(other, TokenType):
            return self.type == other.type

        return self.type != other.type or self.value != other.value

    def __str__(self):
        return f'Token(type={self.type.value} ({self.type.name}), value={repr(self.value)}, start={self.start}, end={self.end}, line={repr(self.line)})'

    __repr__ = __str__

    def copy(self):
        return deepcopy(self)


__all__ = (
    'TokenTypes',
    'TokenType',
    'DummyToken',
    'Token',
)
