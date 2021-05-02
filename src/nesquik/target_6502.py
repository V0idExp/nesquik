from collections import namedtuple
from typing import NamedTuple, Optional

from nesquik.classes import Stage
from nesquik.opcodes import AddrMode, Op, OPCODES
from nesquik.tac import Op as TacOp, Location


class InternalCompilerError(Exception):

    pass


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
        self.stack = {}

    def exec(self, prg):
        # preamble: base pointer initialization, etc
        self.code.extend([
            Instruction(Op.PHA, AddrMode.Implied),

            # base pointer LO
            Instruction(Op.LDA, AddrMode.Immediate, 0xff),
            Instruction(Op.STA, AddrMode.Zeropage, self.baseptr),
            # base pointer HI
            Instruction(Op.LDA, AddrMode.Immediate, 0),
            Instruction(Op.STA, AddrMode.Zeropage, self.baseptr + 1),
        ])

        # transform the IR code to 6502 instructions
        for tac in prg.ir:
            try:
                getattr(self, f'_ir_{tac.op.name.lower()}')(tac)
            except AttributeError:
                print(f'unsupported IR code {tac.op.name}')

        # generate the assembly
        for instr in self.code:
            if instr.mode is AddrMode.Implied:
                prg.asm.append(f'{instr.op.value}')
            elif instr.mode is AddrMode.Immediate:
                prg.asm.append(f'{instr.op.value} #{instr.arg}')
            elif instr.mode in (AddrMode.Zeropage, AddrMode.Absolute):
                prg.asm.append(f'{instr.op.value} ${hex(instr.arg)[2:]}')
            elif instr.mode is AddrMode.IndirectY:
                prg.asm.append(f'{instr.op.value} (${hex(instr.arg)[2:]}),Y')

        prg.code = self.code

    def _ir_add(self, tac):
        if self.a is not None:
            # if A register has a value, check whether it's one of the operands,
            # in order to avoid unnecessary load, and swap the operands if needed

            if self.a == tac.first:
                # first operand already in A, proceed by adding second
                other = tac.second
            elif self.a == tac.second:
                # second operand is already in A, swap with first
                other = tac.first
            else:
                # no operands are in A, save whatever is located in A to stack
                # and load the first operand
                self._push_a()
                self._load_a(tac.first)
                other = tac.second

        else:
            # A is empty, just load the first operand and add the second
            self._load_a(tac.first)
            other = tac.second

        # clear carry flag
        self.code.append(Instruction(Op.CLC, AddrMode.Implied))

        # perform the operation on the value
        self._value_op(tac.dst, other, Op.ADC)

    def _ir_sub(self, tac):
        self._push_a()
        self._load_a(tac.first)

        # set carry flag
        self.code.append(Instruction(Op.SEC, AddrMode.Implied))

        # perform the operation on the value
        self._value_op(tac.dst, tac.second, Op.SBC)

    def _ir_ret(self, tac):
        self._load_a(tac.first)
        self.code.append(Instruction(Op.TAY, AddrMode.Implied))

    def _ir_neg(self, tac):
        self._push_a()
        self._load_a(tac.first)

        self.code.extend([
            Instruction(Op.CLC, AddrMode.Implied),
            Instruction(Op.EOR, AddrMode.Immediate, 255),
            Instruction(Op.ADC, AddrMode.Immediate, 1),
        ])

        if tac.dst.loc is Location.REGISTER:
            self.a = tac.dst
        else:
            raise InternalCompilerError(f'unsupported destination location {tac.dst.loc}')

    def _value_op(self, dst, value, op):
        if value.loc is Location.IMMEDIATE:
            self.code.append(Instruction(op, AddrMode.Immediate, value.value))
        elif value.loc is Location.REGISTER:
            try:
                self.code.extend([
                    Instruction(Op.LDY, AddrMode.Immediate, self.stack[value]),
                    Instruction(op, AddrMode.IndirectY, self.baseptr),
                ])
            except KeyError:
                raise InternalCompilerError(f'register value {value.value} expected to be on stack, but it is not')
        else:
            raise InternalCompilerError(f'unsupported operand location {value.loc}')

        if dst.loc is Location.REGISTER:
            self.a = dst
        else:
            raise InternalCompilerError(f'unsupported destination location {dst.loc}')

    def _push_a(self):
        if self.a is not None:
            self.code.append(Instruction(Op.PHA, AddrMode.Implied))
            self.stack[self.a] = 0xff - len(self.stack)

    def _load_a(self, val):
        if self.a is not None and self.a == val:
            # the value is already in the register
            pass
        elif val.loc is Location.IMMEDIATE:
            self.code.append(Instruction(Op.LDA, AddrMode.Immediate, val.value))
        elif val in self.stack:
            self.code.extend([
                Instruction(Op.LDY, AddrMode.Immediate, self.stack[val]),
                Instruction(Op.LDA, AddrMode.IndirectY, self.baseptr),
            ])
        else:
            raise InternalCompilerError(f'unsupported value location {val.loc}')


class ObjGenerator(Stage):

    def exec(self, prg):
        for instr in prg.code:
            code, size = OPCODES[(instr.op, instr.mode)]
            if size == 1:
                prg.obj.append(code)
            else:
                if instr.arg is None:
                    raise InternalCompilerError(f'instruction {instr.op} expects an argument')
                prg.obj.extend((code, instr.arg))
