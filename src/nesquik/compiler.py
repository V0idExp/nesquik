import re
from dataclasses import dataclass
from enum import Enum
from itertools import count
from typing import List

from lark.tree import Tree
from lark.visitors import Interpreter

from nesquik.ir_generator import IRGenerator
from nesquik.ir_optimizer import IROptimizer
from nesquik.lib import DIV, MUL
from nesquik.opcodes import OPCODES, AddrMode, Op


GLOBAL_LABEL = re.compile(r'^\w{3,}$')


class NESQuikUndefinedVariable(Exception):

    pass


class NESQuikRedefinedVariable(Exception):

    pass


class NESQuikUndefinedLabel(Exception):

    pass


class NESQuikInvalidDereference(Exception):

    pass


class NESQuikSizeError(ValueError):

    pass


class NESQuikStackOverflow(Exception):

    pass


class NESQuikInternalError(Exception):

    pass


class NESQuikUndefinedFunction(Exception):

    pass


class NESQuikBadArgs(Exception):

    pass


class Program:

    def __init__(self, ast, org):
        self.ast = ast
        self.org = org
        self.asm = []
        self.code = []
        self.ir = []
        self.obj = bytearray()


class Reg(Enum):

    A = 'A'
    X = 'X'
    Y = 'Y'


class StackOffset(int):
    pass


class ArgumentOffset(StackOffset):
    pass


class Pointer(int):
    pass


@dataclass
class Variable:
    name: str
    loc: int
    size: int
    is_pointer: bool
    is_array: bool


@dataclass
class Function:
    name: str
    args: List[Variable]


class Stage:

    def exec(self, prg: Program):
        raise NotImplementedError


def parse_int(s):
    if s.startswith('$'):
        return int(s[1:], base=16)
    return int(s, base=10)


class CodeGenerator(Interpreter, Stage):

    def __init__(self):
        super().__init__()
        self.prg = None
        self.registers = {}
        self.global_vars = {}
        self.functions = {}
        self.label_counter = count()
        self.required = {}
        self.scope_offsets = [0]
        self.scope_vars = []
        self.base_ptr = 0x02
        self.arg_base_ptr = 0x04
        self.tmp_ptr = 0x06
        self.reserved = 8

    def exec(self, prg):
        self.prg = prg
        self.visit(prg.ast)

    def ret(self, t):
        expr = t.children[0]
        self.visit(expr)
        if expr.size != 1:
            raise NESQuikSizeError(f'unsupported return value size')
        self._pull(t, expr)
        self._instr(t, Op.TAY)

    def sub(self, t):
        left, right = t.children

        # evaluate right expression
        self.visit(right)
        if right.size != 1:
            raise NESQuikSizeError(f'unsupported sub operand size')
        if isinstance(right.loc, Pointer):
            self._pull(t, right)
        if right.loc is Reg.A:
            self._push(t)

        self.visit(left)
        if left.size != 1:
            raise NESQuikSizeError(f'unsupported sub operand size')
        self._pull(t, left)

        self._instr(t, Op.SEC)
        if isinstance(right.loc, StackOffset):
            self._ldy_offset(t, right)
        self._instr(t, Op.SBC, right)

        self._setloc(t, Reg.A)
        self._setsize(t, 1)

    def add(self, t):
        left, right = t.children

        self.visit(left)
        if left.size != 1:
            raise NESQuikSizeError(f'unsupported add operand size')
        if isinstance(left.loc, Pointer):
            self._pull(t, left)
        if left.loc is Reg.A:
            self._push(t)

        self.visit(right)
        if right.size != 1:
            raise NESQuikSizeError(f'unsupported add operand size')
        self._pull(t, right)

        self._instr(t, Op.CLC)
        if isinstance(left.loc, StackOffset):
            self._ldy_offset(t, left)
        self._instr(t, Op.ADC, left)

        self._setloc(t, Reg.A)
        self._setsize(t, 1)

    def neg(self, t):
        expr = t.children[0]
        self.visit(expr)
        if expr.size != 1:
            raise NESQuikSizeError(f'unsupported neg operand size')
        self._pull(t, expr)

        # perform two's complement negation: invert all bits and add 1
        self._instr(t, Op.CLC)
        self._instr(t, Op.EOR, '#$ff')
        self._instr(t, Op.ADC, '#$01')

        self._setloc(t, Reg.A)
        self._setsize(t, 1)

    def mul(self, t):
        left, right = t.children

        self.visit(left)
        if left.size != 1:
            raise NESQuikSizeError(f'unsupported mul operand size')
        if isinstance(left.loc, Pointer):
            self._pull(t, left)
        if left.loc is Reg.A:
            self._push(t)

        self.visit(right)
        if right.size != 1:
            raise NESQuikSizeError(f'unsupported mul operand size')
        self._pull(t, right)
        self._instr(t, Op.STA, '$0')

        self._pull(t, left)
        self._instr(t, Op.STA, '$1')

        self._instr(t, Op.JSR, self._require(MUL))
        self._setloc(t, Reg.A)
        self._setsize(t, 1)

    def div(self, t):
        left, right = t.children

        self.visit(right)
        if right.size != 1:
            raise NESQuikSizeError(f'unsupported div operand size')
        if isinstance(right.loc, Pointer):
            self._pull(t, right)
        if right.loc is Reg.A:
            self._push(t)

        self.visit(left)
        if left.size != 1:
            raise NESQuikSizeError(f'unsupported div operand size')
        self._pull(t, left)
        self._instr(t, Op.STA, '$0')

        self._pull(t, right)
        self._instr(t, Op.STA, '$1')

        self._instr(t, Op.JSR, self._require(DIV))
        self._setloc(t, Reg.A)
        self._setsize(t, 1)

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
        self._setsize(t, 1)

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
        self._setsize(t, 1)

    def geq(self, t):
        left, right = t.children
        self._geq(t, left, right)
        self._setsize(t, 1)

    def leq(self, t):
        left, right = t.children
        self._geq(t, right, left)
        self._setsize(t, 1)

    def gt(self, t):
        left, right = t.children
        self._gt(t, left, right)
        self._setsize(t, 1)

    def lt(self, t):
        left, right = t.children
        self._gt(t, right, left)
        self._setsize(t, 1)

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
        self._push_scope(t)
        self.visit(expr)
        self._pull(t, expr)
        self._pop_scope(t)

        self._instr(t, Op.CMP, '#0')        # compare the expression result
        self._instr(t, Op.BNE, '@2')        # jump to body if non-zero
        self._instr(t, Op.JMP, '@0')        # jump to the end of the loop if zero

        self._instr(t, None, None, '@2')    # start of the body
        self._push_scope(t)
        self.visit(body)
        self._pop_scope(t)
        self._instr(t, Op.JMP, '@1')        # jump to the start of the loop
        self._instr(t, None, None, '@0')    # end of the loop

    def start(self, t):
        # initialize base pointer HI part
        # NOTE: always 0, wraps around on negative stack indexing for accessing
        # locals
        bp_hi = hex(self.base_ptr + 1)[2:]
        self._instr(t, Op.LDA, '#$00')
        self._instr(t, Op.STA, f'${bp_hi}')

        # initialize arguments base pointer HI part
        # NOTE: always 1, used for positive stack indexing for accessing
        # arguments
        arg_bp_hi = f'${hex(self.arg_base_ptr + 1)[2:]}'
        self._instr(t, Op.LDA, '#$01')
        self._instr(t, Op.STA, arg_bp_hi)

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

    def assign(self, t, size=None):
        name, expr = t.children
        name = name.value

        # attempt to use the node's `loc` first, since this assignment could
        # be part of var's initialization and the name is not yet in the
        # scope
        if hasattr(t, 'loc') and isinstance(t.loc, int):
            loc = t.loc
            if size is None:
                raise NESQuikInternalError(f'unknown size of variable "{name}"')
        else:
            # assigning to an existing var
            var = self._getvar(name)
            size = var.size
            loc = var.loc

        # evaluate the expression
        self.visit(expr)
        self._pull(t, expr)

        # word-sized assignment; LSB = A, MSB = X
        if expr.size == 2:

            if size != 2:
                raise NESQuikSizeError(f'trying to assign a value larger then the size of variable "{name}"')

            # assigning to a stack variable
            if isinstance(loc, StackOffset):
                loc_lo = loc
                loc_hi = type(loc)(loc + 1)
                self._setloc(expr, loc_lo)
                self._ldy_offset(t, expr)
                self._instr(t, Op.STA, expr)
                self._instr(t, Op.TXA)
                self._setloc(expr, loc_hi)
                self._ldy_offset(t, expr)
                self._instr(t, Op.STA, expr)

            # assigning to a global variable
            else:
                self._setloc(expr, loc)
                self._instr(t, Op.STA, expr)
                self._instr(t, Op.TXA)
                self._setloc(expr, loc + 1)
                self._instr(t, Op.STA, expr)
                self._setloc(expr, loc)

        # byte-sized assignment
        else:
            # save it to memory or stack variable
            self._setloc(expr, loc)
            if isinstance(loc, StackOffset):
                self._ldy_offset(t, expr)
            self._instr(t, Op.STA, expr)

    def mem_assign(self, t):
        name, expr = t.children
        name = name.value[1:]

        var = self._getvar(name)
        if not var.is_pointer:
            raise NESQuikInvalidDereference(f'attempting to dereference a non-pointer variable "{name}"')

        # evaluate the expression
        self.visit(expr)
        if isinstance(expr.loc, Pointer):
            self._pull(t, expr)
        if expr.loc is Reg.A:
            self._push(t)

        # prepare the pointer: in case of a pointer located on stack, its low
        # and high parts will be copied to a temporary zero-page location for
        # indirect X addressing;
        # this operation overwrites A register
        self._load_ptr(t, var)
        # load the X offset from zeropage to the pointer
        self._ldx_offset(t, t)

        # pull the expression to A
        self._pull(t, expr)

        # store it via indirect X addressing into the pointed memory location
        self._instr(t, Op.STA, t)

    def imm(self, t):
        literal = t.children[0]
        val = parse_int(literal)
        if val <= 0xff:
            size = 1
        elif val <= 0xffff:
            size = 2
        else:
            raise NESQuikSizeError(f'value "{literal}" is too large')

        self._setsize(t, size)
        self._setloc(t, None)

    def ref(self, t):
        name = t.children[0].value
        var = self._getvar(name)
        loc = var.loc

        # check whether the associated variable is already in the registers to
        # avoid unnecessary pull
        reg_t = self.registers.get(Reg.A)
        if reg_t is not None\
           and reg_t.data in ('assign', 'var', 'ref')\
           and reg_t.children[0].value == name:
            self._setloc(t, Reg.A)
        elif var.is_array:
            # referencing an array involves actually generating a pointer to
            # it's first byte
            self._getref(t, var)
        else:
            self._setloc(t, loc)

        self._setsize(t, 2 if var.is_pointer else 1)

    def deref(self, t):
        name = t.children[0].value
        var = self._getvar(name)
        if not var.is_pointer:
            raise NESQuikInvalidDereference(f'attempting to dereference a non-pointer variable "{name}"')

        self._load_ptr(t, var)
        self._setsize(t, 1)

    def index(self, t):
        # check whether the variable is defined and is a pointer
        name = t.children[0].value
        var = self._getvar(name)
        if not var.is_pointer:
            raise NESQuikInvalidDereference(f'attempting to dereference a non-pointer variable "{name}"')

        # evaluate the index expression and push it to the stack
        index_expr = t.children[1]
        self.visit(index_expr)
        if index_expr.size != 1:
            # TODO: allow 16-bit indices
            raise NESQuikSizeError(f'unsupported index size')
        if isinstance(index_expr.loc, Pointer):
            self._pull(t, index_expr)
        if index_expr.loc is Reg.A:
            self._push(t)

        # copy the pointer to temporary zero-page loaction
        self._load_ptr_to_tmp(t, var)

        # get the index expression result into A
        self._pull(t, index_expr)

        # add it to the pointer LO part
        lo, hi = f'${hex(t.loc)[2:]}', f'${hex(t.loc + 1)[2:]}'
        self._instr(t, Op.CLC)
        self._instr(t, Op.ADC, lo)
        self._instr(t, Op.STA, lo)
        # add the carry to the pointer HI part
        self._instr(t, Op.LDA, hi)
        self._instr(t, Op.ADC, '#0')
        self._instr(t, Op.STA, hi)

        self._setsize(t, 1)

    def index_assign(self, t):
        # check whether the variable is defined and is a pointer
        name, index_expr, expr = t.children
        var = self._getvar(name)
        if not var.is_pointer:
            raise NESQuikInvalidDereference(f'attempting to dereference a non-pointer variable "{name}"')

        # evaluate the index expression and push it to the stack
        self.visit(index_expr)
        if index_expr.size != 1:
            # TODO: allow 16-bit indices
            raise NESQuikSizeError(f'unsupported index size')
        if isinstance(index_expr.loc, Pointer):
            self._pull(t, index_expr)
        if index_expr.loc is Reg.A:
            self._push(t)

        # evaluate the assignment expression and push it to the stack
        self.visit(expr)
        if expr.size != 1:
            raise NESQuikSizeError(f'unsupported assignment value size')
        if isinstance(expr.loc, Pointer):
            self._pull(t, expr)
        if expr.loc is Reg.A:
            self._push(t)

        # copy the pointer to tmp location, since we're going to modify it
        self._load_ptr_to_tmp(t, var)

        # load the index result and add it to the pointer
        self._pull(t, index_expr)

        # LSB is in A, add it to the pointer LO part
        lo, hi = f'${hex(t.loc)[2:]}', f'${hex(t.loc + 1)[2:]}'
        self._instr(t, Op.CLC)
        self._instr(t, Op.ADC, lo)
        self._instr(t, Op.STA, lo)
        # add the carry to the pointer HI part
        self._instr(t, Op.LDA, hi)
        self._instr(t, Op.ADC, '#0')
        self._instr(t, Op.STA, hi)

        # pull the assignment expression result to A
        self._pull(t, expr)

        # store it via indirect X addressing into the pointed memory location
        self._ldx_offset(t, t)
        self._instr(t, Op.STA, t)

    def getref(self, t):
        name = t.children[0].value
        var = self._getvar(name)
        self._getref(t, var)
        self._setsize(t, 2)

    def call(self, t):
        name = t.children[0].value
        try:
            func = self.functions[name]
        except KeyError:
            raise NESQuikUndefinedFunction(f'function "{name}" called but not defined')

        args = t.children[1:]
        if len(args) != len(func.args):
            raise NESQuikBadArgs(f'attempting to call function "{name}" with wrong arguments')

        # evaluate and push the arguments in order
        for i, arg_expr in enumerate(args):
            arg_t = func.args[i]
            self.visit(arg_expr)
            if arg_t.size != arg_expr.size:
                raise NESQuikBadArgs(
                    f'bad call to function "{name}": '
                    f'mismatching size for argument #{i + 1} "{arg_t.name}"')

            self._pull(t, arg_expr)
            if arg_expr.size == 2:
                self._instr(t, Op.TAY)
                self._instr(t, Op.TXA)
                self._instr(t, Op.PHA)
                self._instr(t, Op.TYA)
                self._instr(t, Op.PHA)
            else:
                self._instr(t, Op.PHA)

        self._instr(t, Op.JSR, name)

        if args:
            # restore the stack pointer
            self._instr(t, Op.TSX)
            for _ in range(sum(arg.size for arg in args)):
                self._instr(t, Op.DEX)
            self._instr(t, Op.TXS)

        self._instr(t, Op.TYA)

        self._setloc(t, Reg.A)
        self._setsize(t, 1)

    def var(self, t):
        name = t.children[0].value
        is_pointer = name.startswith('*')
        if is_pointer:
            name = name[1:]
            size = 2
        else:
            size = 1

        scope = self.global_vars if not self.scope_vars else self.scope_vars[-1]
        if name in scope:
            raise NESQuikRedefinedVariable(f'variable "{name}" is already defined')

        if not self.scope_vars:
            # no pushed scopes, allocate a global variable
            loc = self._alloc(size)
            self._setloc(t, loc)
            is_local = False
        else:
            # local variable, the location is a stack offset, assigned
            # previously by func()
            loc = t.loc
            is_local = True

        if len(t.children) > 1:
            # perform the assignment, if there's any initialization expression
            self.assign(t, size=2 if is_pointer else 1)

        var = Variable(
            name=name,
            loc=loc,
            size=size,
            is_pointer=is_pointer,
            is_array=False)

        # map the name to variable's location in memory
        if is_local:
            self.scope_vars[-1][name] = var
        else:
            self.global_vars[name] = var

    def array(self, t):
        name = t.children[0].value

        scope = self.global_vars if not self.scope_vars else self.scope_vars[-1]
        if name in scope:
            raise NESQuikRedefinedVariable(f'variable "{name}" is already defined')

        size = parse_int(t.children[1].value)
        if size > 0xff:
            raise NESQuikSizeError(f'array size exceeds limits: {size}')

        if not self.scope_vars:
            # no pushed scopes, allocate a global variable
            loc = self._alloc(size)
            self._setloc(t, loc)
            is_local = False
        else:
            # local variable, the location is a stack offset, assigned
            # previously by func()
            loc = t.loc
            is_local = True

        var = Variable(
            name=name,
            loc=loc,
            size=size,
            is_pointer=True,
            is_array=True)

        # map the name to variable's location in memory
        if is_local:
            self.scope_vars[-1][name] = var
        else:
            self.global_vars[name] = var

    def func(self, t):
        # TODO:
        # 1) optimization: do not generate stack saving/restoring code if the
        #    function doesn't have any args, locals or temporaries
        # 2) do not generate return value save to Y and restore to A if the
        #    function does not return any values

        # function entry label
        name = t.children[0].value
        self._instr(t, None, None, name)

        # process arguments
        arg_list = self._get_child(t, 'arg_list').children
        args = []
        for arg in arg_list:
            arg_name = arg.children[0].value
            is_pointer = arg.children[0].type == 'PTRNAME'
            if is_pointer:
                size = 2
                arg_name = arg_name[1:]
            else:
                size = 1

            args.append(Variable(arg_name, -1, size, is_pointer, False))

        # assign locations on stack in reverse order
        arg_offset = 3  # offset bp + ret_lo + ret_hi bytes
        for arg in reversed(args):
            arg.loc = ArgumentOffset(arg_offset)
            arg_offset += size

        self.functions[name] = Function(name, args)

        # save current stack pointer as base pointer
        bp_lo = hex(self.base_ptr)[2:]
        self._instr(t, Op.TSX)
        self._instr(t, Op.LDA, f'${bp_lo}')
        self._instr(t, Op.PHA)
        self._instr(t, Op.STX, f'${bp_lo}')

        # if the function expects arguments, prepare also the arguments pointer
        if args:
            arg_bp_lo = hex(self.arg_base_ptr)[2:]
            self._instr(t, Op.STX, f'${arg_bp_lo}')

        # create a new scope
        self._push_scope(t)

        # add arguments to it
        self.scope_vars[-1].update({arg.name: arg for arg in args})

        # reserve stack space for local variables by decrementing SP register by
        # the total size of all locals
        var_list = self._get_child(t, 'var_list').children
        if var_list:
            stack_offset = self.scope_offsets[-1]
            for var in var_list:
                name = var.children[0].value
                is_array = var.data == 'array'
                is_pointer = name.startswith('*') or is_array
                if is_array:
                    size = parse_int(var.children[1])
                elif is_pointer:
                    size = 2
                else:
                    size = 1
                loc = StackOffset(0xff + stack_offset - (size - 1))
                stack_offset -= size
                self._setloc(var, loc)

            locals_size = abs(stack_offset - self.scope_offsets[-1])
            if locals_size > 0:
                if locals_size > 0xff:
                    raise NESQuikStackOverflow(f'stack overflow: function locals too large ({locals_size} bytes)')
                # unless the function stack size is larger then 5 bytes, it's
                # more space-time efficient to decrement the X register with
                # plain `DEX` instructions
                if locals_size <= 5:
                    for _ in range(locals_size + 1):
                        self._instr(t, Op.DEX)
                # subtract with SBC via A the stack size and transfer it to X
                else:
                    self._instr(t, Op.TXA)
                    self._instr(t, Op.SEC)
                    self._instr(t, Op.SBC, f'#{locals_size + 1}')
                    self._instr(t, Op.TAX)
                self._instr(t, Op.TXS)
            self.scope_offsets[-1] = stack_offset

        # initialize the locals and add the body
        self.visit_children(t)

        # pop the scope, but don't bother restoring the stack, it will be reset
        # below before return
        self._pop_scope(t, restore_stack=False)

        # restore stack pointer
        self._instr(t, Op.LDX, f'${bp_lo}')
        self._instr(t, Op.DEX)
        self._instr(t, Op.TXS)
        self._instr(t, Op.PLA)
        self._instr(t, Op.STA, f'${bp_lo}')

        # restore args stack pointer too
        if args:
            self._instr(t, Op.STA, f'${arg_bp_lo}')

        self._instr(t, Op.RTS)

    def _get_child(self, t, type):
        try:
            return [c for c in t.children if getattr(c, 'data', None) == type][0]
        except IndexError:
            return None

    def _cmp(self, t, left, right):
        self.visit(right)
        if right.size != 1:
            raise NESQuikSizeError(f'unsupported cmp operand size')
        if isinstance(right.loc, Pointer):
            self._pull(t, right)
        if right.loc is Reg.A:
            self._push(t)

        self.visit(left)
        if left.size != 1:
            raise NESQuikSizeError(f'unsupported cmp operand size')
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

    def _alloc(self, size):
        offset = self.reserved + sum(var.size for var in self.global_vars.values())
        if offset + size > 255:
            raise NESQuikSizeError(f'out of zero-page memory: cannot statically allocate {size} bytes')
        return offset

    def _ldy_offset(self, t, v):
        if isinstance(v.loc, StackOffset):
            self._instr(t, Op.LDY, f'#${hex(v.loc)[2:]}')

    def _ldx_offset(self, t, v):
        if isinstance(v.loc, Pointer):
            self._instr(t, Op.LDX, f'#${hex(v.loc)[2:]}')

    def _push(self, t):
        v = self.registers.get(Reg.A)
        if v is not None:
            if v.data == 'ref' or v.data == 'var':
                # do not push on stack refs to variables, since they're already
                # in memory
                name = v.children[0].value
                self._setloc(v, self._getvar(name).loc)
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

        # pick the value from stack by dereferencing base pointer + offset using
        # indirect indexed addressing ($ZP),Y
        elif isinstance(arg.loc, StackOffset):
            if arg.size == 2:
                loc_lo = arg.loc
                loc_hi = type(arg.loc)(loc_lo + 1)

                # pull the MSB first from higher byte and store it to X
                self._setloc(arg, loc_hi)
                self._ldy_offset(t, arg)
                self._instr(t, Op.LDA, arg)
                self._instr(t, Op.TAX)

                # pull LSB afterwards from lower byte and store it to A
                self._setloc(arg, loc_lo)
                self._ldy_offset(t, arg)
                self._instr(t, Op.LDA, arg)
            else:
                self._ldy_offset(t, arg)
                self._instr(t, Op.LDA, arg)

        # pick the value from memory by dereferencing a zp-located pointer using
        # indexed indirect addressing ($ZP,X)
        elif isinstance(arg.loc, Pointer):
            if arg.size == 2:
                # load the zero-page offset of the pointer into X
                self._ldx_offset(t, arg)

                # load LSB into A and push it to the stack
                self._instr(t, Op.LDA, arg)
                self._instr(t, Op.PHA)

                # advance the pointer to MSB:
                ptr_lo = f'${hex(arg.loc)[2:]}'
                ptr_hi = f'${hex(arg.loc + 1)[2:]}'
                # ... add 1 to pointer's low address part
                self._instr(t, Op.LDA, ptr_lo)
                self._instr(t, Op.CLC)
                self._instr(t, Op.ADC, '#1')
                self._instr(t, Op.STA, ptr_lo)
                # ... add the carry to pointer's high address part
                self._instr(t, Op.LDA, ptr_hi)
                self._instr(t, Op.ADC, '#0')
                self._instr(t, Op.STA, ptr_lo)

                # load MSB into A and transfer it to X
                self._instr(t, Op.LDA, arg)
                self._instr(t, Op.TAX)

                # pull LSB back into A
                self._instr(t, Op.PLA)
            else:
                # load the byte into A by indirect indexing
                self._ldx_offset(t, arg)
                self._instr(t, Op.LDA, arg)

        # pick the value from memory using absolute addressing
        elif isinstance(arg.loc, int):
            self._instr(t, Op.LDA, arg)
            if arg.size == 2:
                self._setloc(arg, arg.loc + 1)
                self._instr(t, Op.LDX, arg)

        # an immediate, just fill the registers
        else:
            value = parse_int(arg.children[0])
            self._instr(t, Op.LDA, f'#{value & 0xff}')
            if arg.size == 2:
                self._instr(t, Op.LDX, f'#{(value >> 8) & 0xff}')

        self._setloc(arg, Reg.A)

    def _getref(self, t, var):
        # stack variable
        if isinstance(var.loc, StackOffset):
            # add the stack offset to base pointer LO address and push the result to the stack
            self._instr(t, Op.LDA, f'${hex(self.base_ptr)[2:]}')
            self._instr(t, Op.CLC)
            self._instr(t, Op.ADC, f'#{var.loc}')
            self._instr(t, Op.PHA)

            # add the eventual carry to the base pointer HI address and move it to X
            self._instr(t, Op.LDA, f'${hex(self.base_ptr + 1)[2:]}')
            self._instr(t, Op.ADC, f'#0')
            self._instr(t, Op.TAX)

            # pop from the stack the LO address
            self._instr(t, Op.PLA)

        # global variable
        else:
            lo = var.loc & 0xff
            hi = var.loc >> 8
            self._instr(t, Op.LDA, f'#{lo}')
            self._instr(t, Op.LDX, f'#{hi}')

        self._setloc(t, Reg.A)

    def _load_ptr(self, t, var):
        # if the pointer is located on stack, copy the address to a temporary
        # pointer located at zero-page in order to perform indexed indirect
        # addressing
        if isinstance(var.loc, StackOffset):
            tmp_ptr_lo = f'${hex(self.tmp_ptr)[2:]}'
            tmp_ptr_hi = f'${hex(self.tmp_ptr + 1)[2:]}'

            if var.is_array:
                # load into A, X the *stack location address*, at which the array begins
                self._getref(t, var)
                self._instr(t, Op.STA, tmp_ptr_lo)
                self._instr(t, Op.TXA)
                self._instr(t, Op.STA, tmp_ptr_hi)
            else:
                # create two fake byte-sized "anchors" to the stack-located address
                # LO and HI parts
                addr_lo, addr_hi = Tree(None, []), Tree(None, [])
                self._setloc(addr_lo, var.loc)
                self._setsize(addr_lo, 1)
                self._setloc(addr_hi, type(var.loc)(var.loc + 1))
                self._setsize(addr_hi, 1)

                # pull the LO part and store it into temporary pointer LO location
                self._pull(t, addr_lo)
                self._instr(t, Op.STA, tmp_ptr_lo)

                # pull the HI part and store it in related part of the temporary
                # pointer
                self._pull(t, addr_hi)
                self._instr(t, Op.STA, tmp_ptr_hi)

            # now the location of the tree is the temporary pointer of the zero
            # page memory
            self._setloc(t, Pointer(self.tmp_ptr))

        # the pointer is in a global variable and is already in zero-page memory
        else:
            self._setloc(t, Pointer(var.loc))

    def _load_ptr_to_tmp(self, t, var):
        if isinstance(var.loc, StackOffset):
            self._load_ptr(t, var)
        else:
            tmp_ptr_lo = f'${hex(self.tmp_ptr)[2:]}'
            tmp_ptr_hi = f'${hex(self.tmp_ptr + 1)[2:]}'

            if var.is_array:
                ptr_lo = f'#{var.loc}'
                ptr_hi = f'#0'
            else:
                ptr_lo = f'${hex(var.loc)[2:]}'
                ptr_hi = f'${hex(var.loc+ 1)[2:]}'
            self._instr(t, Op.LDA, ptr_lo)
            self._instr(t, Op.STA, tmp_ptr_lo)
            self._instr(t, Op.LDA, ptr_hi)
            self._instr(t, Op.STA, tmp_ptr_hi)
            self._setloc(t, Pointer(self.tmp_ptr))

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

    def _setsize(self, t, size):
        setattr(t, 'size', size)

    def _instr(self, t, op, arg=None, label=None):
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
                if isinstance(arg.loc, ArgumentOffset):
                    mode = AddrMode.IndirectY
                    arg = self.arg_base_ptr
                elif isinstance(arg.loc, StackOffset):
                    mode = AddrMode.IndirectY
                    arg = self.base_ptr
                elif isinstance(arg.loc, Pointer):
                    mode = AddrMode.IndirectX
                    arg = 0
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
        elif mode is AddrMode.IndirectX:
            line = f'{op.value} (${hex(arg)[2:]},X)'
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
    IRGenerator,
    IROptimizer,
    # CodeGenerator,
    # AddressInjector,
    # Assembler,
]


def compile(ast, org):
    prg = Program(ast, org)

    for stage_cls in STAGES:
        stage = stage_cls()
        stage.exec(prg)

    return prg
