import re
from enum import Enum
from itertools import count

from lark.visitors import Interpreter

from nesquik.lib import DIV, MUL
from nesquik.opcodes import OPCODES, AddrMode, Op


GLOBAL_LABEL = re.compile(r'^\w{3,}$')


class NESQuikUndefinedVariable(Exception):

    pass


class NESQuikRedefinedVariable(Exception):

    pass


class NESQuikUndefinedLabel(Exception):

    pass


class NESQuikInternalError(Exception):

    pass


class NESQuikUndefinedFunction(Exception):

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
        self.global_vars = {}
        self.functions = {}
        self.reserved = 4
        self.label_counter = count()
        self.required = {}
        self.scope_offsets = [0]
        self.scope_vars = []
        self.base_ptr = 0x02

    def exec(self, prg):
        self.prg = prg
        self.visit(prg.ast)

    def ret(self, t):
        self.visit_children(t)
        self._pull(t, t.children[0])

    def sub(self, t):
        left, right = t.children

        self.visit(right)
        if right.loc is Reg.A:
            self._push(t)

        self.visit(left)
        self._pull(t, left)

        self._instr(t, Op.SEC)
        self._ldy_offset(t, right)
        self._instr(t, Op.SBC, right)
        self._setloc(t, Reg.A)

    def add(self, t):
        left, right = t.children

        self.visit(left)
        if left.loc is Reg.A:
            self._push(t)

        self.visit(right)
        self._pull(t, right)

        self._instr(t, Op.CLC)
        if isinstance(left.loc, StackOffset):
            self._ldy_offset(t, left)
        self._instr(t, Op.ADC, left)
        self._setloc(t, Reg.A)

    def neg(self, t):
        arg = t.children[0]
        self.visit(arg)
        self._pull(t, arg)

        # perform two's complement negation: invert all bits and add 1
        self._instr(t, Op.CLC)
        self._instr(t, Op.EOR, '#$ff')
        self._instr(t, Op.ADC, '#$01')

        self._setloc(t, Reg.A)

    def mul(self, t):
        left, right = t.children

        self.visit(left)
        if left.loc is Reg.A:
            self._push(t)

        self.visit(right)
        self._pull(t, right)
        self._instr(t, Op.STA, '$0')

        self._pull(t, left)
        self._instr(t, Op.STA, '$1')

        self._instr(t, Op.JSR, self._require(MUL))
        self._setloc(t, Reg.A)

    def div(self, t):
        left, right = t.children

        self.visit(right)
        if right.loc is Reg.A:
            self._push(t)

        self.visit(left)
        self._pull(t, left)
        self._instr(t, Op.STA, '$0')

        self._pull(t, right)
        self._instr(t, Op.STA, '$1')

        self._instr(t, Op.JSR, self._require(DIV))
        self._setloc(t, Reg.A)

    def eq(self, t):
        # TODO: try to swap the operands if one of them is supposed to be
        # already in A
        left, right = t.children
        self._cmp(t, left, right)
        self._instr(t, Op.BEQ, '@0')
        self._instr(t, Op.LDA, '#0')
        self._instr(t, Op.BEQ, '@1')
        self._instr(t, Op.LDA, '#1', '@0')
        self._instr(t, None, None, '@1')
        self._setloc(t, Reg.A)

    def neq(self, t):
        # TODO: try to swap the operands if one of them is supposed to be
        # already in A
        left, right = t.children
        self._cmp(t, left, right)
        self._instr(t, Op.CMP, right)
        self._instr(t, Op.BNE, '@0')
        self._instr(t, Op.LDA, '#0')
        self._instr(t, Op.BNE, '@1')
        self._instr(t, Op.LDA, '#1', '@0')
        self._instr(t, None, None, '@1')
        self._setloc(t, Reg.A)

    def geq(self, t):
        left, right = t.children
        self._geq(t, left, right)

    def leq(self, t):
        left, right = t.children
        self._geq(t, right, left)

    def gt(self, t):
        left, right = t.children
        self._gt(t, left, right)

    def lt(self, t):
        left, right = t.children
        self._gt(t, right, left)

    def if_stmt(self, t):
        # local labels counter
        c = count(0)
        end_label = f'@{next(c)}'

        for i, stmt in enumerate(t.children):
            is_last = i == len(t.children) - 1

            branch_i, true_i = next(c), next(c)

            # label for the branch itself
            branch_lbl = f'@{branch_i}'

            # label for true condition
            true_lbl = f'@{true_i}'

            # label for false condition, matches the branch_lbl of the next loop;
            # note that `c` does not advance
            false_lbl = f'@{true_i + 1}'

            # set a label for the current branch, to which the previous (if any)
            # would jump in case its expression evaluates to false
            self._instr(t, None, None, branch_lbl)

            if stmt.data != 'else_branch':
                # `if` and `elif` have expressions and a body
                expr, block = stmt.children
            else:
                # `else` has only a body
                expr, block = None, stmt.children[0]

            if expr is not None:
                # perform expression evaluation in it's own scope
                self._push_scope(t)
                self.visit(expr)
                self._pop_scope(t)

                # expression result comparison
                self._instr(t, Op.CMP, '#0')

                # branch to either the body or jump to the next block
                self._instr(t, Op.BNE, true_lbl)
                if is_last:
                    self._instr(t, Op.JMP, end_label)
                else:
                    self._instr(t, Op.JMP, false_lbl)

            # the actual branch body
            self._instr(t, None, None, true_lbl)
            self._push_scope(t)
            self.visit(block)
            self._pop_scope(t)

            # jump to the end after body execution
            if not is_last:
                self._instr(t, Op.JMP, end_label)

        # end label
        self._instr(t, None, None, end_label)

    def while_stmt(self, t):
        expr, body = t.children[0], t.children[1]

        self._instr(t, None, None, '@1')    # start of the loop
        self.visit(expr)
        self._pull(t, expr)
        self._instr(t, Op.CMP, '#0')        # compare the expression result
        self._instr(t, Op.BNE, '@2')        # jump to body if non-zero
        self._instr(t, Op.JMP, '@0')        # jump to the end of the loop if zero
        self._instr(t, None, None, '@2')    # start of the body
        self.visit(body)
        self._instr(t, Op.JMP, '@1')        # jump to the start of the loop
        self._instr(t, None, None, '@0')    # end of the loop

    def start(self, t):
        # initialize base pointer HI part (always 0, wraps around on indexed
        # addressing)
        bp_hi = hex(self.base_ptr + 1)[2:]
        self._instr(t, Op.LDA, '#$00')
        self._instr(t, Op.STA, f'${bp_hi}')

        # define global variables
        var_list = self._get_child(t, 'var_list')
        self.visit(var_list)

        # add a jump to `main` function
        self._instr(t, Op.JSR, 'main')
        # BRK instruction at the end
        self._instr(t, Op.BRK)

        # define functions
        func_list = self._get_child(t, 'func_list')
        for func in func_list.children:
            self.visit(func)
            name = func.children[0].value
            self.functions[name] = func

        if 'main' not in self.functions:
            raise NESQuikUndefinedFunction(f'function "main" required but not defined')

        # define required subroutines
        for name, subroutine in self.required.items():
            self._resetlabels(t)
            # add a global label at the subroutine start
            self._instr(t, None, None, name)

            # append the actual subroutine instructions
            for instr in subroutine.code:
                self._instr(t, *instr)

    def assign(self, t):
        name, expr = t.children
        name = name.value

        if hasattr(t, 'loc') and isinstance(t.loc, int):
            # attempt to use the node's `loc` first, since this assignment could
            # be part of var's initialization and the name is not yet in the
            # scope
            loc = t.loc
        else:
            # assigning to an existing var
            loc = self._getvar(name)

        self.visit(expr)
        self._pull(t, expr)
        self._store(t, loc)

    def imm(self, t):
        self._setloc(t, None)

    def ref(self, t):
        name = t.children[0].value
        loc = self._getvar(name)

        # check whether the associated variable is already in the registers to
        # avoid unnecessary pull
        reg_t = self.registers.get(Reg.A)
        if reg_t is not None\
           and reg_t.data in ('assign', 'var', 'ref')\
           and reg_t.children[0].value == name:
            self._setloc(t, Reg.A)
        else:
            self._setloc(t, loc)

    def call(self, t):
        name = t.children[0].value
        if name not in self.functions:
            raise NESQuikUndefinedFunction(f'function "{name}" called but not defined')

        self._instr(t, Op.JSR, name)
        self._setloc(t, Reg.A)

    def var(self, t):
        name = t.children[0].value

        scope = self.global_vars if not self.scope_vars else self.scope_vars[-1]
        if name in scope:
            raise NESQuikRedefinedVariable(f'variable "{name}" is already defined')

        if not self.scope_vars:
            # no pushed scopes, allocate a global variable
            loc = self._alloc()
            self._setloc(t, loc)
            is_local = False
        else:
            # local variable, the location is a stack offset, assigned
            # previously by func()
            loc = t.loc
            is_local = True

        if len(t.children) > 1:
            # perform the assignment, if there's any initialization expression
            self.assign(t)

        # map the name to variable's location in memory
        if is_local:
            self.scope_vars[-1][name] = loc
        else:
            self.global_vars[name] = loc

    def func(self, t):
        # function entry label
        name = t.children[0].value
        self._instr(t, None, None, name)

        # save current stack pointer as base pointer
        bp_lo = hex(self.base_ptr)[2:]
        self._instr(t, Op.TSX)
        self._instr(t, Op.LDA, f'${bp_lo}')
        self._instr(t, Op.PHA)
        self._instr(t, Op.STX, f'${bp_lo}')

        # create a new scope
        self._push_scope(t)

        # reserve stack space for local variables by decrementing SP register
        var_list = self._get_child(t, 'var_list').children
        if var_list:
            stack_offset = self.scope_offsets[-1]
            for var in var_list:
                loc = StackOffset(0xff + stack_offset)
                stack_offset -= 1
                self._setloc(var, loc)
                self._instr(t, Op.DEX)

            self._instr(t, Op.TXS)
            self.scope_offsets[-1] = stack_offset

        # initialize the locals and add the body
        self.visit_children(t)

        # pop the scope, but don't bother restoring the stack, it will be reset
        # below before return
        self._pop_scope(t, restore_stack=False)

        # save A to Y
        self._instr(t, Op.TAY)

        # restore stack pointer
        self._instr(t, Op.LDX, f'${bp_lo}')
        self._instr(t, Op.DEX)
        self._instr(t, Op.TXS)
        self._instr(t, Op.PLA)
        self._instr(t, Op.STA, f'${bp_lo}')

        # restore A
        self._instr(t, Op.TYA)

        self._instr(t, Op.RTS)

    def _get_child(self, t, type):
        try:
            return [c for c in t.children if getattr(c, 'data', None) == type][0]
        except IndexError:
            return None

    def _cmp(self, t, left, right):
        self.visit(right)
        if right.loc is Reg.A:
            self._push(t)

        self.visit(left)
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
        self._instr(t, Op.BCS, '@0')
        self._instr(t, Op.BEQ, '@0')
        self._instr(t, Op.LDA, '#0')
        self._instr(t, Op.BEQ, '@1')
        self._instr(t, Op.LDA, '#1', '@0')
        self._instr(t, None, None, '@1')
        self._setloc(t, Reg.A)

    def _getvar(self, name):
        scopes = [self.global_vars] + self.scope_vars
        while scopes:
            scope = scopes.pop(-1)
            if name in scope:
                return scope[name]

        raise NESQuikUndefinedVariable(f'use of undefined variable {name}')

    def _alloc(self):
        return self.reserved + len(self.global_vars)

    def _store(self, t, loc):
        v = self.registers[Reg.A]
        self._setloc(v, loc)
        if isinstance(v.loc, StackOffset):
            self._ldy_offset(t, v)
        self._instr(t, Op.STA, v)

    def _ldy_offset(self, t, v):
        if isinstance(v.loc, StackOffset):
            self._instr(t, Op.LDY, f'#${hex(v.loc)[2:]}')

    def _push(self, t):
        v = self.registers.get(Reg.A)
        if v is not None:
            if v.data == 'ref' or v.data == 'var':
                # do not push on stack refs to variables, since they're already
                # in memory
                name = v.children[0].value
                self._setloc(v, self._getvar(name))
            else:
                # use the current scope's stack offset
                stack_offset = self.scope_offsets[-1]

                # Negative offsets relative to the base pointer rely on overflow
                # when doing `(bp),Y` indirect addressing.
                # For example, with base pointer located at $02 and pointing to $a0,
                # to index a value 2 bytes higher in the stack (lower in memory), we
                # do:
                # ldy #$fe
                # lda ($02),Y  ; $00a0 + $fe = $019e
                offset = StackOffset(0xff + stack_offset)

                # decrease the stack offset
                self.scope_offsets[-1] -= 1

                self._setloc(v, offset)
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

    def _push_scope(self, t):
        self.registers.clear()
        self.scope_offsets.append(self.scope_offsets[-1])
        self.scope_vars.append({})

    def _pop_scope(self, t, restore_stack=True):
        # if the stack offset changed in relation to previous scope during
        # condition expression evaluation, pop the inserted elements from the
        # stack
        pop_count = abs(self.scope_offsets[-1] - self.scope_offsets[-2])
        if restore_stack and pop_count > 0:
            self._instr(t, Op.TSX)
            for _ in range(pop_count):
                self._instr(t, Op.INX)
            self._instr(t, Op.TXS)

        self.scope_vars.pop(-1)
        self.scope_offsets.pop(-1)
        self.registers.clear()

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
