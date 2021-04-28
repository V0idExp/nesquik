from itertools import count

from lark.visitors import Interpreter

from nesquik.classes import Stage
from nesquik.tac import TAC, Label, Location, Op, Value


class IRGenerator(Interpreter, Stage):

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
        labels = [Label(self._alloc_label()) for _ in range(len(t.children))]
        end_label = labels[-1]

        for i, branch in enumerate(t.children):
            is_last_branch = i == len(t.children) - 1

            if i > 0:
                self.code.append(TAC(Op.EMPTY, dst=None, label=labels[i - 1]))

            # condition branch (if, elif)
            if len(branch.children) > 1:
                cond, body = branch.children
                self.visit(cond)
                self.code.append(TAC(Op.IF_Z, dst=labels[i], first=cond.val))
                self.visit(body)

                if not is_last_branch:
                    self.code.append(TAC(Op.JMP, dst=end_label))

            # conditionless branch (else)
            else:
                self.visit(branch)

        self.code.append(TAC(Op.EMPTY, label=end_label))

    def ret(self, t):
        self.visit_children(t)
        expr = t.children[0]
        self.code.append(TAC(Op.RET, first=expr.val))

    def _alloc_reg(self):
        return next(self.regcounter)

    def _alloc_label(self):
        return next(self.lblcounter)

    def _binop(self, t, op):
        left, right = t.children
        self.visit_children(t)

        reg = self._alloc_reg()
        value = Value(Location.REGISTER, reg)
        self.code.append(TAC(op, value, left.val, right.val))
        self._setval(t, value)


    def _setval(self, t, val):
        setattr(t, 'val', val)
