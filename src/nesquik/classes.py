from abc import ABCMeta, abstractmethod

from nesquik.tac import TAC


class Program:
    """
    A NESQuik program.

    A program is initially just a source code listing, by passing via various
    compiler stages, it is populated with additional data.
    """

    # Original source code
    source: list[str]
    # Parsed Abstract Syntax Tree
    ast: any
    # Code segment offset in memory
    org: int
    # Intermediate Representation code, as sequence of Three-Address-Code
    # objects
    ir: list[TAC]
    # Target architecture code (implementation-specific)
    code: any
    # Target architecture assembly source code
    asm: list[str]
    # Target architecture bytecode
    obj: bytearray

    def __init__(self, source: list[str], org: int):
        self.source = source
        self.org = org
        self.ast = None
        self.asm = []
        self.ir = []
        self.obj = bytearray()


class Stage(metaclass=ABCMeta):
    """
    A compiler stage that performs some manipulations of the Program object.
    """

    @abstractmethod
    def exec(self, prg: Program):
        pass
