import pytest
from nesquik.compiler import compile
from nesquik.parser import parse
from py65.devices.mpu6502 import MPU


class CPU(MPU):

    def __init__(self):
        super().__init__()

    def compile_and_run(self, code):
        self.reset()

        org = 0xc000

        ast = parse(code)
        prg = compile(ast, org=org)
        obj = prg.obj

        self.memory[org:org + len(obj)] = obj
        self.pc = org

        while not self.p & self.INTERRUPT:
            self.step()

        return prg


@pytest.fixture
def cpu():
    return CPU()
