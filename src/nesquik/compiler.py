import re
from enum import Enum
from itertools import count

from lark.visitors import Interpreter

from nesquik.lib import MUL, DIV
from nesquik.opcodes import OPCODES, AddrMode, Op


GLOBAL_LABEL = re.compile(r'^\w{3,}$')


class NESQuikUndefinedVariable(Exception):

    pass


class NESQuikUndefinedLabel(Exception):

    pass


class NESQuikInternalError(Exception):

    pass


class Program:

    def __init__(self, ast, org):
        self.ast = ast
        self.org = org
        self.asm = []
        self.code = []
        self.obj = bytearray()


class Reg(Enum):

    A = 'A'
    X = 'X'
    Y = 'Y'


class Stage:

    def exec(self, prg: Program):
        raise NotImplementedError


class CodeGenerator(Interpreter, Stage):

    def __init__(self):
        super().__init__()
        self.prg = None
        self.registers = {}
        self.addrtable = [None] * 0xff
        self.vars = {}
        self.reserved = 2
        self.label_counter = count()
        self.required = {}

    def exec(self, prg):
        self.prg = prg
        self.visit(prg.ast)

    def ret(self, t):
        self.visit_children(t)
        self._pull(t, t.children[0])

    def sub(self, t):
        self.visit_children(t)
        left, right = t.children

        self._instr(t, Op.SEC)

        if left.loc is Reg.A:
            # if left operand is already in A, subtract the right
            self._instr(t, Op.SBC, right)
            self._free(right)
        else:
            # load left to A and subtract the right
            self._push(Reg.A)
            self._pull(t, left)
            self._instr(t, Op.SBC, right)
            self._free(right)

        self._setloc(t, Reg.A)

    def add(self, t):
        self.visit_children(t)
        left, right = t.children

        self._instr(t, Op.CLC)

        if left.loc is Reg.A:
            # if left operand is already in A, add the right
            self._instr(t, Op.ADC, right)
            self._free(right)
        elif right.loc is Reg.A:
            # if right operand is already in A, add the left
            self._instr(t, Op.ADC, left)
            self._free(left)
        else:
            # none of the operands are in A, load left to A and add the right
            self._push(Reg.A)
            self._pull(t, left)
            self._instr(t, Op.ADC, right)
            self._free(right)

        self._setloc(t, Reg.A)

    def neg(self, t):
        self.visit_children(t)
        arg = t.children[0]

        if arg.loc is not Reg.A:
            self._push(Reg.A)
            self._pull(t, arg)

        # perform two's complement negation: invert all bits and add 1
        self._instr(t, Op.CLC)
        self._instr(t, Op.EOR, '#$ff')
        self._instr(t, Op.ADC, '#$01')

        self._setloc(t, Reg.A)

    def mul(self, t):
        self.visit_children(t)
        left, right = t.children

        self._push(Reg.A)
        self._pull(t, left, Reg.X)
        self._pull(t, right, Reg.Y)
        self._instr(t, Op.JSR, self._require(MUL))
        self._setloc(t, Reg.A)

    def div(self, t):
        self.visit_children(t)
        left, right = t.children

        self._push(Reg.A)
        self._pull(t, left)
        self._instr(t, Op.STA, '$0')
        self._pull(t, right)
        self._instr(t, Op.STA, '$1')
        self._instr(t, Op.JSR, self._require(DIV))
        self._setloc(t, Reg.A)

    def start(self, t):
        self.visit_children(t)

        if self.required:
            # if there are any required subroutines, they'll be added at the end
            # of the code, separate them for previous code with a BRK
            # instruction
            self._instr(t, Op.BRK)

        for name, subroutine in self.required.items():
            self._resetlabels(t)
            # add a global label at the subroutine start
            self._instr(t, None, None, name)

            # append the actual subroutine instructions
            for instr in subroutine.code:
                self._instr(t, *instr)

    def assign(self, t):
        self.visit_children(t)
        name, expr = t.children
        name = name.value

        if isinstance(expr.loc, int):
            # expression already in memory, pin it there
            self.vars[name] = expr.loc
        else:
            # if the expression is an immediate, load it into A
            if expr.loc is None:
                self._pull(t, expr, Reg.A)

            # expression in registers, allocate memory for it and store it there
            loc = self._alloc(t)
            self.vars[name] = loc
            self._store(t, expr.loc, loc)

    def imm(self, t):
        self._setloc(t, None)

    def ref(self, t):
        name = t.children[0].value

        try:
            self._setloc(t, self.vars[name])
        except KeyError:
            raise NESQuikUndefinedVariable(f'undefined variable {name}')

    def _alloc(self, t):
        try:
            return next(i for i in range(self.reserved, len(self.addrtable)) if self.addrtable[i] is None)
        except StopIteration:
            raise NESQuikInternalError(f'out of scratch memory')

    def _push(self, reg=Reg.A):
        t = self.registers.get(reg)
        if t is not None and not isinstance(t.loc, int):
            i = self._alloc(t)
            self._setloc(t, i)

            op = {
                Reg.A: Op.STA,
                Reg.X: Op.STX,
                Reg.Y: Op.STY
            }[reg]
            self._instr(t, op, t)

    def _store(self, t, reg, loc):
        v = self.registers[reg]
        op = {
            Reg.A: Op.STA,
            Reg.X: Op.STX,
            Reg.Y: Op.STY
        }[reg]
        self._setloc(v, loc)
        self._instr(t, op, v)

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
        if isinstance(t.loc, int) and not t.loc in self.vars.values():
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

        if op is None:
            # empty instruction, no mode
            mode = None
        elif arg is None:
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
            elif GLOBAL_LABEL.match(arg):
                # global label, use absolute addressing
                mode = AddrMode.Absolute
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

        # if the label starts with '@' it's a placeholder, generate the actual
        # string for it
        if label is not None and label.startswith('@'):
            label = self._getlabel(t, label)

        self.prg.code.append((op, mode, arg, label))

        if op is None:
            line = ''
        elif mode in (AddrMode.Implied, AddrMode.Accumulator):
            line = op.value
        elif mode is AddrMode.Zeropage:
            line = f'{op.value} ${hex(arg)[2:]}'
        elif mode is AddrMode.Immediate:
            line = f'{op.value} #{arg}'
        elif mode in (AddrMode.Relative, AddrMode.Absolute):
            line = f'{op.value} {arg}'
        else:
            raise NESQuikInternalError(f'unsupported addr mode {mode}')

        line = ((f'{label}:' if label else '') + '\t' + line)
        if line.strip():
            self.prg.asm.append(line)

    def _getlabel(self, t, label):
        if not hasattr(t, 'labels'):
            setattr(t, 'labels', {})

        if label in t.labels:
            return t.labels[label]

        label_id = f'L{next(self.label_counter)}'
        t.labels[label] = label_id
        return label_id

    def _resetlabels(self, t):
        setattr(t, 'labels', {})

    def _require(self, subroutine):
        self.required.setdefault(subroutine.name, subroutine)
        return subroutine.name


class AddressInjector(Stage):

    def __init__(self):
        self.offset = 0
        self.labels = {}

    def exec(self, prg):
        self._compute_offsets(prg.code)
        self._inject_offsets(prg.org, prg.code)

    def _compute_offsets(self, code):
        self.offset = 0
        for op, mode, _, label in code:
            if op is not None:
                _, size = OPCODES[(op, mode)]
            else:
                # empty instructions do not change the size
                size = 0

            if label is not None:
                self.labels[label] = self.offset

            self.offset += size

    def _inject_offsets(self, org, code):
        self.offset = 0
        for i, (op, mode, arg, label) in enumerate(code):
            if op is not None:
                _, size = OPCODES[(op, mode)]
            else:
                # empty instructions do not change the size
                size = 0

            if isinstance(arg, str):
                # a label is found
                try:
                    label_offset = self.labels[arg]
                except KeyError:
                    raise NESQuikUndefinedLabel(f'undefined label {arg}')

                if mode is AddrMode.Relative:
                    # in relative addressing, the argument is a displacement
                    # from current instruction;
                    # NOTE: the -2 below is for compensating the current
                    # comparison instruction size
                    offset = label_offset - self.offset
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

                code[i] = (op, mode, offset, label)

            self.offset += size


class Assembler(Stage):

    def __init__(self):
        self.size = 0

    def exec(self, prg):
        for op, mode, arg, _ in prg.code:
            if op is None:
                continue

            try:
                opcode, size = OPCODES[(op, mode)]
            except KeyError:
                raise NESQuikInternalError('unsupported operand size')

            prg.obj.append(opcode)
            if arg is not None:
                if mode is AddrMode.Absolute and size == 3:
                    # in absolute addressing, the address low part is coming
                    # first, then the hi
                    arg_hi = arg >> 8
                    arg_lo = arg & 0xff
                    prg.obj.append(arg_lo)
                    prg.obj.append(arg_hi)
                elif size == 2:
                    prg.obj.append(arg)

            elif size != 1:
                raise NESQuikInternalError('mismatching address mode and argument size')


STAGES = [
    CodeGenerator,
    AddressInjector,
    Assembler,
]


def compile(ast, org):
    prg = Program(ast, org)

    for stage_cls in STAGES:
        stage = stage_cls()
        stage.exec(prg)

    return prg
