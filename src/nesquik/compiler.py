from enum import Enum, IntEnum
from itertools import count

from lark import Visitor

from nesquik.lib import MUL
from nesquik.opcodes import OPCODES, AddrMode, Op


class NESQuikError(Exception):

    def __init__(self, tree, *args):
        super().__init__(*args)
        self.tree = tree

    def __str__(self):
        return f'line {self.tree.meta.line}: {self.args[0]}'


class NESQuikUndefinedVariable(NESQuikError):

    def __init__(self, tree, var_name):
        super().__init__(tree)
        self.var_name = var_name

    def __str__(self):
        return super().__str__() + f': variable "{self.var_name}" used but not defined'


class NESQuikUndefinedLabel(NESQuikError):

    def __init__(self, tree, name):
        super().__init__(tree)
        self.name = name

    def __str__(self):
        return super().__str__() + f': label "{self.name}" used but not defined'


class NESQuikInternalError(NESQuikError):

    pass


class Program:

    def __init__(self):
        self.asm = []
        self.obj = bytearray()


class VarsChecker(Visitor):

    def __init__(self, _):
        self.vars = {}

    def assign(self, tree):
        name = tree.children[0].value
        self.vars[name] = tree

    def ref(self, tree):
        name = tree.children[0].value
        if name not in self.vars:
            raise NESQuikUndefinedVariable(tree, name)



class Reg(Enum):

    A = 'A'
    X = 'X'
    Y = 'Y'


class CodeGenerator(Visitor):

    def __init__(self, prg):
        self.prg = prg
        self.registers = {}
        self.addrtable = [None] * 0xff
        self.reserved = 2
        self.label_counter = count()

    def ret(self, t):
        self._pull(t, t.children[0])

    def sub(self, t):
        self._instr(t, Op.SEC)
        left, right = t.children

        # if left operand is already in A, subtract the right
        if left.loc is Reg.A:
            self._instr(t, Op.SBC, right)
            self._free(right)
        else:
            self._push()
            self._pull(t, left)
            self._instr(t, Op.SBC, right)
            self._free(right)

        self._setloc(t, Reg.A)

    def add(self, t):
        self._instr(t, Op.CLC)
        left, right = t.children

        # if left operand is already in A, add the right
        if left.loc is Reg.A:
            self._instr(t, Op.ADC, right)
            self._free(right)

        # if right operand is already in A, add the left
        elif right.loc is Reg.A:
            self._instr(t, Op.ADC, left)
            self._free(left)

        # none of the operands are in A
        else:
            # save A
            self._push()
            self._pull(t, left)
            self._instr(t, Op.ADC, right)
            self._free(right)

        self._setloc(t, Reg.A)

    def imm(self, t):
        self._setloc(t, None)

    def neg(self, t):
        arg = t.children[0]
        self._push()

        # load arg into A
        self._pull(t, arg)

        # perform two's complement negation: invert all bits and add 1
        self._instr(t, Op.CLC)
        self._instr(t, Op.EOR, '#$ff')
        self._instr(t, Op.ADC, '#$01')

        self._setloc(t, Reg.A)

    def mul(self, t):
        left, right = t.children

        self._push(Reg.A)
        self._pull(t, left, Reg.X)
        self._pull(t, right, Reg.Y)

        for instr in MUL.code:
            self._instr(t, *instr)

        self._free(left)
        self._free(right)
        self._setloc(t, Reg.A)

    def _push(self, reg=Reg.A):
        t = self.registers.get(reg)
        if t is not None:
            try:
                i = next(i for i in range(self.reserved, len(self.addrtable)) if self.addrtable[i] is None)
            except StopIteration:
                raise NESQuikInternalError(t, 'out of temporary memory')

            self._setloc(t, i)

            op = {
                Reg.A: Op.STA,
                Reg.X: Op.STX,
                Reg.Y: Op.STY
            }[reg]
            self._instr(t, op, t)

    def _pull(self, t, arg, reg=Reg.A):
        if arg.loc is reg:
            # do nothing, argument already in place
            return
        elif isinstance(arg.loc, Reg):
            # transfer register to register
            tx_ops = {
                (Reg.A, Reg.X): Op.TAX,
                (Reg.A, Reg.Y): Op.TAY,
                (Reg.X, Reg.A): Op.TXA,
                (Reg.Y, Reg.A): Op.TYA,
            }
            try:
                # try to move arg between X,Y and A
                op = tx_ops[(arg.loc, reg)]
                self._instr(t, op)
            except KeyError:
                # X <-> Y move, need to transfer via A
                self._push(Reg.A)
                if reg is Reg.X:
                    self._instr(t, Op.TXA)
                else:
                    self._instr(t, Op.TYA)

                op = tx_ops[(Reg.A, reg)]
                self._instr(t, op)
        else:
            # either immediate or memory
            op = {
                Reg.A: Op.LDA,
                Reg.X: Op.LDX,
                Reg.Y: Op.LDY,
            }[reg]
            self._instr(t, op, arg)

        self._setloc(arg, reg)

    def _free(self, t):
        if isinstance(t.loc, int):
            self.addrtable[t.loc] = None

    def _setloc(self, t, loc):
        if hasattr(t, 'loc'):
            self._free(t)

        if isinstance(loc, Reg):
            # add to registers
            self.registers[loc] = t
        elif isinstance(loc, int):
            self.addrtable[loc] = t

        setattr(t, 'loc', loc)

    def _instr(self, t, op, arg=None, label=None):

        def parse_int(s):
            if s.startswith('$'):
                return int(s[1:], base=16)
            return int(s, base=10)

        if arg is None:
            # no arg, argument is implied in the command
            mode = AddrMode.Implied
        elif isinstance(arg, str):
            # arg can be:
            #   * a numeric immediate, ex: #123, #$f0
            #   * a zero-page address, ex: $1b, $ff
            #   * an absolute address, ex: $0100, $c123
            #   * a label placeholder, ex: @1, @global_label
            #   * the accumulator register name
            #   * address index (TODO)
            if arg.startswith('#'):
                # numeric immediate
                mode = AddrMode.Immediate
                arg = parse_int(arg[1:])
            elif arg.startswith('$'):
                # address
                arg = parse_int(arg)
                if arg <= 0xff:
                    mode = AddrMode.Zeropage
                else:
                    mode = AddrMode.Absolute
            elif arg.startswith('@'):
                # label placeholder
                mode = AddrMode.Relative
                arg = self._getlabel(t, arg)
            elif arg == 'a':
                # accumulator
                arg = None
                mode = AddrMode.Accumulator
        else:
            # arg is a tree node
            if arg.loc is None:
                # not located anywhere, thus, an immediate
                mode = AddrMode.Immediate
                arg = parse_int(arg.children[0])
            elif isinstance(arg.loc, int):
                # memory location
                # TODO: support for absolute addresses?
                mode = AddrMode.Zeropage
                arg = arg.loc

        if label is not None:
            label = self._getlabel(t, label)

        code = getattr(t, 'code', [])
        code.append((op, mode, arg, label))
        setattr(t, 'code', code)

        if mode in (AddrMode.Implied, AddrMode.Accumulator):
            line = op.value
        elif mode is AddrMode.Zeropage:
            line = f'{op.value} ${hex(arg)[2:]}'
        elif mode is AddrMode.Immediate:
            line = f'{op.value} #{hex(arg)[2:]}'
        elif mode is AddrMode.Relative:
            line = f'{op.value} {arg}'
        else:
            raise NESQuikInternalError(t, f'unsupported addr mode {mode}')

        line = (f'{label}:' if label else '') + '\t' + line
        self.prg.asm.append(line)

    def _getlabel(self, t, label):
        if not hasattr(t, 'labels'):
            setattr(t, 'labels', {})

        if label in t.labels:
            return t.labels[label]

        label_id = f'{t.data}{next(self.label_counter)}'.upper()
        t.labels[label] = label_id
        return label_id


class OffsetInjector(Visitor):

    class Phase(Enum):

        COMPUTE_OFFSETS = 0
        INJECT_OFFSETS = 1

    def __init__(self, prg):
        self.prg = prg
        self.offset = 0
        self.labels = {}
        self.phase = OffsetInjector.Phase.COMPUTE_OFFSETS

    def __default__(self, t):
        for i, (op, mode, arg, label) in enumerate(getattr(t, 'code', [])):
            _, size = OPCODES[(op, mode)]

            if self.phase is OffsetInjector.Phase.COMPUTE_OFFSETS:
                if label is not None:
                    self.labels[label] = self.offset

            elif isinstance(arg, str):
                # a label is found
                try:
                    label_offset = self.labels[arg]
                    offset = label_offset - self.offset
                    if offset < 0:
                        offset = 0x100 + (offset - 2)
                    else:
                        offset -= 2
                    t.code[i] = (op, mode, offset, label)

                except KeyError:
                    raise NESQuikUndefinedLabel(t, arg)

            self.offset += size

    def start(self, t):
        if self.phase is OffsetInjector.Phase.COMPUTE_OFFSETS:
            self.phase = OffsetInjector.Phase.INJECT_OFFSETS
            self.offset = 0
            self.visit(t)


class Assembler(Visitor):

    def __init__(self, prg):
        self.prg = prg
        self.size = 0

    def __default__(self, t):
        for op, mode, arg, _ in getattr(t, 'code', []):
            opcode, size = OPCODES[(op, mode)]
            if size > 2:
                raise NESQuikInternalError(t, 'unsupported operand size')
            else:
                self.prg.obj.append(opcode)
                if arg is not None:
                    self.prg.obj.append(arg)

PASSES = [
    (VarsChecker, True),
    (CodeGenerator, False),
    (OffsetInjector, False),
    (Assembler, False),
]


def compile(ast):
    prg = Program()

    for cls, top_down in PASSES:
        v = cls(prg)
        if top_down:
            v.visit_topdown(ast)
        else:
            v.visit(ast)

    return prg
