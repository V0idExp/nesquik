import pytest
from nesquik.classes import Program
from nesquik.ir_generator import IRGenerator
from nesquik.parser import Parser
from py65.devices.mpu6502 import MPU


class CPU(MPU):

    def __init__(self):
        super().__init__()
        # NOTE: change this value to the number of reserved compiler bytes
        self.zp_offset = 0x08

    def compile(self, code):
        self.reset()

        prg = Program(source=code, org=0xc000)

        stages = [
            Parser(),
            IRGenerator(),
        ]

        for stage in stages:
            stage.exec(prg)

        self.memory[prg.org:prg.org + len(prg.obj)] = prg.obj
        self.pc = prg.org

        return prg

    def compile_and_run(self, code):
        prg = self.compile(code)

        while not self.p & self.INTERRUPT:
            self.step()

        return prg


@pytest.fixture
def cpu():
    return CPU()
