from enum import Enum
from itertools import count
from lark.visitors import Interpreter


class Op(Enum):

    ALLOC   = 'alloc'
    ADD     = '+'
    SUB     = '-'
    MUL     = '*'
    DIV     = '/'
    EQ      = '=='
    NEQ     = '!='
    GEQ     = '>='
    GT      = '>'
    LEQ     = '<='
    LT      = '<'
    IF_Z    = 'if_z'
    IF_NZ   = 'if_nz'
    JMP     = 'jmp'
    RET     = 'ret'
    EMPTY   = ''


class Location(Enum):

    IMMEDIATE = 'immediate'
    REGISTER = 'register'
    CODE = 'code'


class Value:

    def __init__(self, loc: Location, value: int):
        self.loc = loc
        self.value = value

    def __str__(self):
        return f'{self.value}'


class TAC:

    def __init__(self, op: Op, dst, first, second=None, label=None):
        self.op = op
        self.dst = dst
        self.first = first
        self.second = second
        self.label = label


class Assignment(TAC):

    pass


class BinOp(TAC):

    pass


class Branch(TAC):

    def __init__(self, if_nonzero, label, cond):
        super().__init__(Op.IF_NZ if if_nonzero else Op.IF_Z, label, cond)


class Goto(TAC):

    def __init__(self, label):
        super().__init__(Op.JMP, label, None)


class Label(TAC):

    def __init__(self, label):
        super().__init__(Op.EMPTY, None, None, None, label)


class Return(TAC):

    def __init__(self, expr):
        super().__init__(Op.RET, None, expr, None, None)


class IRGenerator(Interpreter):

    def __init__(self):
        self.code = []
        self.regcounter = count()
        self.lblcounter = count()

    def exec(self, prg):
        self.visit(prg.ast)
        prg.ir = self.code

    def imm(self, t):
        s = t.children[0]
        if s.startswith('$'):
            val = int(s[1:], base=16)
        else:
            val = int(s, base=10)

        self._setval(t, Value(Location.IMMEDIATE, val))

    def sub(self, t):
        self._binop(t, Op.SUB)

    def add(self, t):
        self._binop(t, Op.ADD)

    def div(self, t):
        self._binop(t, Op.DIV)

    def mul(self, t):
        self._binop(t, Op.MUL)

    def eq(self, t):
        self._binop(t, Op.EQ)

    def neq(self, t):
        self._binop(t, Op.NEQ)

    def geq(self, t):
        self._binop(t, Op.GEQ)

    def gt(self, t):
        self._binop(t, Op.GT)

    def leq(self, t):
        self._binop(t, Op.LEQ)

    def lt(self, t):
        self._binop(t, Op.LT)

    def if_stmt(self, t):
        labels = [Value(Location.CODE, self._alloc_label()) for _ in range(len(t.children))]
        end_label = labels[-1]

        for i, branch in enumerate(t.children):
            is_last_branch = i == len(t.children) - 1

            if i > 0:
                self.code.append(Label(labels[i - 1]))

            # condition branch (if, elif)
            if len(branch.children) > 1:
                cond, body = branch.children
                self.visit(cond)
                self.code.append(Branch(False, labels[i], cond.val))
                self.visit(body)

                if not is_last_branch:
                    self.code.append(Goto(end_label))

            # conditionless branch (else)
            else:
                self.visit(branch)

        self.code.append(Label(end_label))

    def ret(self, t):
        self.visit_children(t)
        expr = t.children[0]
        self.code.append(Return(expr.val))

    def _alloc_reg(self):
        return next(self.regcounter)

    def _alloc_label(self):
        return next(self.lblcounter)

    def _binop(self, t, op):
        left, right = t.children
        self.visit_children(t)

        reg = self._alloc_reg()
        value = Value(Location.REGISTER, reg)
        self.code.append(BinOp(op, value, left.val, right.val))
        self._setval(t, value)

    def _setval(self, t, val):
        setattr(t, 'val', val)
