import pytest
from lark import Token, Transformer, Tree, v_args
from nesquik.compiler import compile
from nesquik.parser import parse
from py65.assembler import Assembler
from py65.devices.mpu6502 import MPU
from itertools import chain


# The py65 assembler accepts only hex digits, this transformer converts all
# decimals to hexadecimals
class HexImmOnly(Transformer):

    @v_args(inline=True)
    def imm(self, t):
        if t.type == 'INT':
            intval = int(t.value, base=10)
            hexval = f'${hex(intval)[2:]}'
            t = Token('HEXINT', hexval)
        return Tree('imm', [t])


class CPU(MPU):

    def __init__(self):
        super().__init__()
        self.assembler = Assembler(self)

    def compile_and_run(self, code):
        self.reset()

        ast = parse(code, transforms=[HexImmOnly])
        asm = compile(ast)

        obj = list(chain.from_iterable(self.assembler.assemble(line) for line in asm))

        self.memory[0xc000:0xc000 + len(obj)] = obj
        self.pc = 0xc000

        for _ in range(len(asm)):
            self.step()

    def __repr__(self):
        return object.__repr__(self)


@pytest.fixture
def cpu():
    return CPU()


@pytest.fixture
def assembler(cpu):
    return Assembler(cpu)
