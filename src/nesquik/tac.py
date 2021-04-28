from dataclasses import dataclass
from enum import Enum


class Op(Enum):

    ALLOC   = 'alloc'
    ADD     = '+'
    SUB     = '-'
    MUL     = '*'
    DIV     = '/'
    EQ      = '=='
    NEQ     = '!='
    GEQ     = '>='
    GT      = '>'
    LEQ     = '<='
    LT      = '<'
    IF_Z    = 'if_z'
    JMP     = 'jmp'
    RET     = 'ret'
    EMPTY   = ''


class Location(Enum):

    IMMEDIATE = 'immediate'
    REGISTER = 'register'
    CODE = 'code'


class Value:

    def __init__(self, loc: Location, value: int):
        self.loc = loc
        self.value = value

    def __str__(self):
        return f'{self.value}'


class Label(Value):

    def __init__(self, value: int):
        super().__init__(Location.CODE, value)


@dataclass
class TAC:

    op: Op
    dst: Value = None
    first: Value = None
    second: Value = None
    label: Label = None
