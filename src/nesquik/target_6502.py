from collections import namedtuple
from itertools import chain
from typing import NamedTuple, Optional, Union

from nesquik.classes import Stage
from nesquik.opcodes import OPCODES, AddrMode, Op
from nesquik.tac import Location
from nesquik.tac import Op as TacOp


class InternalCompilerError(Exception):

    pass


class Instruction(NamedTuple):

    op: Op
    mode: AddrMode
    arg: Optional[Union[int, str]] = None
    label: Optional[str] = None


# Multiplication subroutine.
# $0 - first operand
# $1 - second operand
# A  - result
#
# http://6502org.wikidot.com/software-math-intmul
_MUL_SUBROUTINE = (
    Instruction(Op.LDX, AddrMode.Immediate, 8, label='mul'),
    Instruction(Op.ASL, AddrMode.Implied, label='mul0'),
    Instruction(Op.ASL, AddrMode.Zeropage, 0),
    Instruction(Op.BCC, AddrMode.Relative, 'mul1'),
    Instruction(Op.CLC, AddrMode.Implied),
    Instruction(Op.ADC, AddrMode.Zeropage, 1),
    Instruction(Op.DEX, AddrMode.Implied, label='mul1'),
    Instruction(Op.BNE, AddrMode.Relative, 'mul0'),
    Instruction(Op.RTS, AddrMode.Implied),
)


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
        self.requires = {}

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

        # add the required subroutines
        self.code.extend(chain.from_iterable(self.requires.values()))

        # generate the assembly
        for instr in self.code:
            label = f'{instr.label}:\t' if instr.label else '\t'
            if instr.mode is AddrMode.Implied:
                prg.asm.append(f'{label}{instr.op.value}')
            elif instr.mode is AddrMode.Immediate:
                prg.asm.append(f'{label}{instr.op.value} #{instr.arg}')
            elif instr.mode in (AddrMode.Zeropage, AddrMode.Absolute):
                arg = f'${hex(instr.arg)[2:]}' if isinstance(instr.arg, int) else instr.arg
                prg.asm.append(f'{label}{instr.op.value} {arg}')
            elif instr.mode is AddrMode.IndirectY:
                prg.asm.append(f'{label}{instr.op.value} (${hex(instr.arg)[2:]}),Y')
            elif instr.mode is AddrMode.Relative:
                prg.asm.append(f'{label}{instr.op.value} {instr.arg}')
            else:
                raise InternalCompilerError(f'unsupported address mode {instr.mode.name}')

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

    def _ir_mul(self, tac):
        if 'mul' not in self.requires:
            self.requires['mul'] = _MUL_SUBROUTINE

        if self.a is not None:
            if self.a == tac.first:
                other = tac.second
            elif self.a == tac.second:
                other = tac.first
            else:
                self._push_a()
                self._load_a(tac.first)
                other = tac.second
        else:
            self._load_a(tac.first)
            other = tac.second

        self.code.append(Instruction(Op.STA, AddrMode.Zeropage, 0))
        self._load_a(other)
        self.code.append(Instruction(Op.STA, AddrMode.Zeropage, 1))
        self.code.append(Instruction(Op.JSR, AddrMode.Absolute, 'mul'))

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


class AddressInjector(Stage):

    def __init__(self):
        self.labels = {}

    def exec(self, prg):
        self._compute_offsets(prg.code)
        self._inject_offsets(prg.org, prg.code)

    def _compute_offsets(self, code):
        offset = 0

        for instr in code:
            _, size = OPCODES[(instr.op, instr.mode)]

            if instr.label is not None:
                self.labels[instr.label] = offset

            offset += size

    def _inject_offsets(self, org, code):
        total_size = 0

        for i, instr in enumerate(code):
            op, mode, arg, label = instr
            _, size = OPCODES[(op, mode)]

            if isinstance(arg, str):
                # a label is found
                try:
                    label_offset = self.labels[arg]
                except KeyError:
                    raise InternalCompilerError(f'undefined label {arg}')

                if mode is AddrMode.Relative:
                    # in relative addressing, the argument is a displacement
                    # from current instruction;
                    # NOTE: the -2 below is for compensating the current
                    # comparison instruction size
                    offset = label_offset - total_size
                    if offset < 0:
                        # negative displacements are specified as two's
                        # complement signed numbers
                        offset = 0x100 + (offset - 2)
                    else:
                        offset -= 2
                else:
                    # in absolute addressing, add the org address to the
                    # offset
                    offset = org + label_offset

                arg = offset

                code[i] = Instruction(op, mode, arg, label)

            total_size += size


class ObjGenerator(Stage):

    def exec(self, prg):
        for instr in prg.code:
            try:
                opcode, size = OPCODES[(instr.op, instr.mode)]
            except KeyError:
                raise InternalCompilerError('unsupported operand size')

            prg.obj.append(opcode)

            if instr.arg is not None:
                if instr.mode is AddrMode.Absolute and size == 3:
                    # in absolute addressing, the address low part is coming
                    # first, then the hi
                    arg_hi = instr.arg >> 8
                    arg_lo = instr.arg & 0xff
                    prg.obj.append(arg_lo)
                    prg.obj.append(arg_hi)
                elif size == 2:
                    prg.obj.append(instr.arg)
            elif size != 1:
                raise InternalCompilerError('mismatching address mode and argument size')


STAGES = [
    AsmGenerator,
    AddressInjector,
    ObjGenerator,
]
