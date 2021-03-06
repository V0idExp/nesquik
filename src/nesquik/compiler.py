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


class StackOffset(int):
    pass


class Stage:

    def exec(self, prg: Program):
        raise NotImplementedError


class CodeGenerator(Interpreter, Stage):

    def __init__(self):
        super().__init__()
        self.prg = None
        self.registers = {}
        self.vars = {}
        self.reserved = 4
        self.label_counter = count()
        self.required = {}
        self.stack_offset = 0
        self.base_ptr = 0x02

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
        else:
            # load left to A and subtract the right
            self._push()
            self._pull(t, left)

            if isinstance(right.loc, StackOffset):
                self._ldy_offset(t, right)
            self._instr(t, Op.SBC, right)

        self._setloc(t, Reg.A)

    def add(self, t):
        self.visit_children(t)
        left, right = t.children

        self._instr(t, Op.CLC)

        if left.loc is Reg.A:
            # if left operand is already in A, add the right
            if isinstance(right.loc, StackOffset):
                self._ldy_offset(t, right)
            self._instr(t, Op.ADC, right)
        elif right.loc is Reg.A:
            # if right operand is already in A, add the left
            if isinstance(left.loc, StackOffset):
                self._ldy_offset(t, left)
            self._instr(t, Op.ADC, left)
        else:
            # none of the operands are in A, load left to A and add the right
            self._push()
            self._pull(t, left)
            if isinstance(right.loc, StackOffset):
                self._ldy_offset(t, right)
            self._instr(t, Op.ADC, right)

        self._setloc(t, Reg.A)

    def neg(self, t):
        self.visit_children(t)
        arg = t.children[0]

        if arg.loc is not Reg.A:
            self._push()
            self._pull(t, arg)

        # perform two's complement negation: invert all bits and add 1
        self._instr(t, Op.CLC)
        self._instr(t, Op.EOR, '#$ff')
        self._instr(t, Op.ADC, '#$01')

        self._setloc(t, Reg.A)

    def mul(self, t):
        self.visit_children(t)
        left, right = t.children

        self._push()
        self._pull(t, left)
        self._instr(t, Op.STA, '$0')
        self._pull(t, right)
        self._instr(t, Op.STA, '$1')
        self._instr(t, Op.JSR, self._require(MUL))
        self._setloc(t, Reg.A)

    def div(self, t):
        self.visit_children(t)
        left, right = t.children

        self._push()
        self._pull(t, left)
        self._instr(t, Op.STA, '$0')
        self._pull(t, right)
        self._instr(t, Op.STA, '$1')
        self._instr(t, Op.JSR, self._require(DIV))
        self._setloc(t, Reg.A)

    def eq(self, t):
        self.visit_children(t)
        left, right = t.children

        if right.loc is Reg.A:
            self._cmp(t, right, left)
        else:
            self._cmp(t, left, right)
        self._instr(t, Op.BEQ, '@0')
        self._instr(t, Op.LDA, '#0')
        self._instr(t, Op.BEQ, '@1')
        self._instr(t, Op.LDA, '#1', '@0')
        self._instr(t, None, None, '@1')
        self._setloc(t, Reg.A)

    def neq(self, t):
        self.visit_children(t)
        left, right = t.children

        if right.loc is Reg.A:
            self._cmp(t, right, left)
        else:
            self._cmp(t, left, right)
        self._instr(t, Op.CMP, right)
        self._instr(t, Op.BNE, '@0')
        self._instr(t, Op.LDA, '#0')
        self._instr(t, Op.BNE, '@1')
        self._instr(t, Op.LDA, '#1', '@0')
        self._instr(t, None, None, '@1')
        self._setloc(t, Reg.A)

    def geq(self, t):
        self.visit_children(t)
        left, right = t.children
        self._geq(t, left, right)

    def leq(self, t):
        self.visit_children(t)
        left, right = t.children
        self._geq(t, right, left)

    def gt(self, t):
        self.visit_children(t)
        left, right = t.children
        self._gt(t, left, right)

    def lt(self, t):
        self.visit_children(t)
        left, right = t.children
        self._gt(t, right, left)

    def if_stmt(self, t):
        for i, stmt in enumerate(t.children):
            is_last = i == len(t.children) - 1

            if len(stmt.children) > 1:
                # `if` and `elif` have expressions
                expr, block = stmt.children
            else:
                # `else` does not
                expr, block = None, stmt.children[0]

            if i > 0:
                # set an enter label for the block, if not `if`
                self._instr(t, None, None, f'@{i}')

            if expr is not None:
                self.visit(expr)

                # evaluate the expression, which is already in A, since the
                # previously performed comparison result is stored in A
                self._instr(t, Op.CMP, '#1')

                if is_last:
                    # branch to the end
                    self._instr(t, Op.BNE, f'@0')
                else:
                    # branch to next block, if there's any
                    self._instr(t, Op.BNE, f'@{i + 1}')

            # the actual branch body
            self.visit(block)

            # jump to the end after body execution
            if not is_last:
                self._instr(t, Op.JMP, '@0')

        # end label
        self._instr(t, None, None, '@0')

    def start(self, t):
        lo = hex(self.base_ptr)[2:]
        hi = hex(self.base_ptr + 1)[2:]

        # base pointer HI part is always 0
        self._instr(t, Op.LDA, '#$00')
        self._instr(t, Op.STA, f'${hi}')

        # save current stack pointer
        self._instr(t, Op.TSX)
        self._instr(t, Op.TXA)
        self._instr(t, Op.PHA)
        self._instr(t, Op.STA, f'${lo}')

        self.visit_children(t)

        # TODO: uncomment these when multiple stack frames are implemented
        # restore stack pointer
        # self._instr(t, Op.LDX, f'${lo}')
        # self._instr(t, Op.TXS)
        # self._instr(t, Op.PLA)
        # self._instr(t, Op.STA, f'${lo}')

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

        self._pull(t, expr)

        loc = self._getvar(name)
        self._store(t, loc)
        self.registers[Reg.A] = t

    def imm(self, t):
        self._setloc(t, None)

    def ref(self, t):
        name = t.children[0].value
        loc = self._getvar(name)

        # check whether the associated variable is already in the registers
        reg_t = self.registers.get(Reg.A)
        if reg_t.data == 'var' and not isinstance(reg_t.loc, StackOffset) and reg_t.loc == loc:
            self._setloc(t, Reg.A)
        else:
            self._setloc(t, loc)

    def var(self, t):
        # on declaration, allocate memory for the variable and pin it in vars map
        name = t.children[0].value
        loc = self._alloc()
        self.vars[name] = loc
        self._setloc(t, loc)

        if len(t.children) > 1:
            # perform the assignment, if there's any initialization expression
            self.assign(t)

    def _cmp(self, t, left, right):
        if left.loc is not Reg.A:
        self._push()
        self._pull(t, left)
        if isinstance(right.loc, StackOffset):
            self._ldy_offset(t, right)

        self._instr(t, Op.CMP, right)

    def _gt(self, t, left, right):
        self._cmp(t, left, right)
        self._instr(t, Op.BCC, '@0')
        self._instr(t, Op.BEQ, '@0')
        self._instr(t, Op.LDA, '#1')
        self._instr(t, Op.BNE, '@1')
        self._instr(t, Op.LDA, '#0', '@0')
        self._instr(t, None, None, '@1')
        self._setloc(t, Reg.A)

    def _geq(self, t, left, right):
        self._cmp(t, left, right)
        self._instr(t, Op.LDA, '#0')
        self._instr(t, Op.ADC, '#0')
        self._setloc(t, Reg.A)

    def _getvar(self, name):
        try:
            return self.vars[name]
        except KeyError:
            raise NESQuikUndefinedVariable(f'use of undefined variable {name}')

    def _alloc(self):
        return self.reserved + len(self.vars) + 1

    def _store(self, t, loc):
        v = self.registers[Reg.A]
        self._setloc(v, loc)
        self._instr(t, Op.STA, v)

    def _ldy_offset(self, t, v):
        if isinstance(v.loc, StackOffset):
            self._instr(t, Op.LDY, f'#${hex(v.loc)[2:]}')

    def _push(self):
        t = self.registers.get(Reg.A)
        if t is not None:
            # Negative offsets relative to the base pointer rely on overflow
            # when doing `(bp),Y` indirect addressing.
            # For example, with base pointer located at $02 and pointing to $a0,
            # to index a value 2 bytes higher in the stack (lower in memory), we
            # do:
            # ldy #$fe
            # lda ($02),Y  ; $00a0 + $fe = $019e
            offset = StackOffset(0xff + self.stack_offset)
            self.stack_offset -= 1
            self._setloc(t, offset)
            self._instr(t, Op.PHA)

    def _pull(self, t, arg):
        if arg.loc is Reg.A:
            # do nothing, argument already in place
            return
        elif isinstance(arg.loc, StackOffset):
            # pick the value from the stack using indirect addressing
            self._ldy_offset(t, arg)
            self._instr(t, Op.LDA, arg)
        else:
            # either immediate or memory
            self._instr(t, Op.LDA, arg)

        self._setloc(arg, Reg.A)

    def _setloc(self, t, loc):
        if isinstance(loc, Reg):
            # add to registers
            self.registers[loc] = t

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
                if op is Op.JMP:
                    mode = AddrMode.Absolute
                else:
                    mode = AddrMode.Relative
                arg = self._getlabel(t, arg)
            elif GLOBAL_LABEL.match(arg):
                # global label, use absolute addressing
                mode = AddrMode.Absolute
        else:
            # arg is a tree node
            if arg.loc is None:
                # not located anywhere, thus, an immediate
                mode = AddrMode.Immediate
                arg = parse_int(arg.children[0])
            else:
                if isinstance(arg.loc, StackOffset):
                    mode = AddrMode.IndirectY
                    arg = self.base_ptr
                else:
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
        elif mode is AddrMode.Implied:
            line = op.value
        elif mode is AddrMode.Zeropage:
            line = f'{op.value} ${hex(arg)[2:]}'
        elif mode is AddrMode.Immediate:
            line = f'{op.value} #{arg}'
        elif mode in (AddrMode.Relative, AddrMode.Absolute):
            line = f'{op.value} {arg}'
        elif mode is AddrMode.IndirectY:
            line = f'{op.value} (${hex(arg)[2:]}),Y'
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
