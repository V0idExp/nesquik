from collections import namedtuple
from typing import NamedTuple, Optional

from nesquik.classes import Stage
from nesquik.opcodes import AddrMode, Op
from nesquik.tac import Op as TacOp, Location


class Instruction(NamedTuple):

    op: Op
    mode: AddrMode
    arg: Optional[int] = None


class AsmGenerator(Stage):

    def __init__(self):
        self.a = None
        self.x = None
        self.y = None
        self.code = []

        self.tmp = {
            i: None for i in range(4)
        }

        self.baseptr = 0x04
        self.stack_index = 0xff

        self.ir_transformers = {
            TacOp.ADD: self._add,
        }

    def exec(self, prg):
        # preamble: base pointer initialization, etc
        self.code.extend([
            Instruction(Op.LDA, AddrMode.Immediate, 0),
            Instruction(Op.STA, AddrMode.Zeropage, self.baseptr),
            Instruction(Op.LDA, AddrMode.Immediate, 0xff),
            Instruction(Op.STA, AddrMode.Zeropage, self.baseptr + 1),
        ])

        # transform the IR code to 6502 instructions
        for tac in prg.ir:
            try:
                self.ir_transformers[tac.op](tac)
            except KeyError:
                print(f'unsupported IR code {tac.op.name}')

        # generate the assembly
        for instr in self.code:
            if instr.mode is AddrMode.Implied:
                prg.asm.append(f'{instr.op.value}')
            elif instr.mode is AddrMode.Immediate:
                prg.asm.append(f'{instr.op.value} #{instr.arg}')
            elif instr.mode in (AddrMode.Zeropage, AddrMode.Absolute):
                prg.asm.append(f'{instr.op.value} ${hex(instr.arg)[2:]}')

    def _add(self, tac):
        self._push_a()
        self._load_a(tac.first)
        # push A to stack
        # load first into A
        # add second
        pass

    def _push_a(self):
        if self.a is not None:
            self.code.append(Instruction(Op.PHA, AddrMode.Implied))

    def _load_a(self, val):
        if val.loc is Location.IMMEDIATE:
            self.code.append(Instruction(Op.LDA, AddrMode.Immediate, val.value))
        elif val.loc is Location.REGISTER:
            self.code.append(Instruction(Op.LDA, AddrMode.IndirectY, val.value))
        else:
            raise RuntimeError(f'unsupported value location {val.loc}')



class ObjGenerator(Stage):

    def exec(self, prg):
        pass
