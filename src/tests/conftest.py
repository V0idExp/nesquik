import pytest
from nesquik.compiler import compile
from nesquik.parser import parse
from py65.devices.mpu6502 import MPU


class CPU(MPU):

    def __init__(self):
        super().__init__()

    def compile_and_run(self, code):
        self.reset()

        ast = parse(code)
        prg = compile(ast)
        obj = prg.obj

        self.memory[0xc000:0xc000 + len(obj)] = obj
        self.pc = 0xc000

        while not self.p & self.INTERRUPT:
            self.step()

        return prg


@pytest.fixture
def cpu():
    return CPU()
