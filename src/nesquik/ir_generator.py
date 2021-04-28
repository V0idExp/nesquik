from enum import Enum
from itertools import count
from lark.visitors import Interpreter


class Op(Enum):

    IMM8    = 'imm8'
    IMM16   = 'imm16'
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
    IF_Z    = 'if_zero'
    IF_NZ   = 'if_nonzero'
    GOTO    = 'goto'
    EMPTY   = ''


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
        super().__init__(Op.GOTO, label, None)


class Label(TAC):

    def __init__(self, label):
        super().__init__(Op.EMPTY, None, None, None, label)


class IRGenerator(Interpreter):

    def __init__(self):
        self.code = []
        self.tmpcounter = count()
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

        if val <= 0xff:
            op = Op.IMM8
        elif val <= 0xffff:
            op = Op.IMM16
        else:
            raise ValueError(f'value "{s}" is too large')

        loc = self._alloc()
        self.code.append(Assignment(op, loc, val))
        self._setloc(t, loc)

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
        labels = [self._alloc_label() for _ in range(len(t.children))]
        end_label = labels[-1]

        for i, branch in enumerate(t.children):
            is_last_branch = i == len(t.children) - 1

            if i > 0:
                self.code.append(Label(labels[i - 1]))

            # condition branch (if, elif)
            if len(branch.children) > 1:
                cond, body = branch.children
                self.visit(cond)
                self.code.append(Branch(False, labels[i], cond.loc))
                self.visit(body)

                if not is_last_branch:
                    self.code.append(Goto(end_label))

            # conditionless branch (else)
            else:
                self.visit(branch)

        self.code.append(Label(end_label))

    def _alloc(self):
        return f'%{next(self.tmpcounter)}'

    def _alloc_label(self):
        return f'@{next(self.lblcounter)}'

    def _binop(self, t, op):
        left, right = t.children
        self.visit_children(t)

        loc = self._alloc()
        self.code.append(BinOp(op, loc, left.loc, right.loc))
        self._setloc(t, loc)

    def _setloc(self, t, loc):
        setattr(t, 'loc', loc)
