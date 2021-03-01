from lark import Visitor, Transformer, v_args
from enum import Enum


class NESQuikError(Exception):

    def __init__(self, tree):
        self.tree = tree

    def __str__(self):
        return f'line {self.tree.meta.line}'


class NESQuikUndefinedVariable(NESQuikError):

    def __init__(self, tree, var_name):
        super().__init__(tree)
        self.var_name = var_name

    def __str__(self):
        return super().__str__() + f': variable "{self.var_name}" used but not defined'


class NESQuikInternalError(NESQuikError):

    pass


class Program:

    def __init__(self):
        self.symtable = {}
        self.code = []


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
        self.addrtable = {i: None for i in range(0xff)}

    def ret(self, t):
        result = t.children[0]
        if result.loc is None:
            self._code(f'lda #{result.loc}')
        elif result.loc is Reg.A:
            pass
        elif result.loc is Reg.X:
            self._code(f'txa')
        elif result.loc is Reg.Y:
            self._code(f'tya')
        else:
            addr = hex(result.loc)[2:]
            self._code(f'lda ${addr}')

        # self._code(f'rts')

    def sub(self, t):
        self._code('sec')

        left, right = t.children
        # if left operand is already in A, subtract the right
        if left.loc is Reg.A:
            # if right is an immediate
            if right.loc is None:
                # just subtract it
                self._code(f'sbc #{right.children[0]}')
            else:
                # subtract from zero-page
                self._code(f'sbc ${hex(right.loc)[2:]}')

        else:
            self._save_a()

            if left.loc is None:
                self._code(f'lda #{left.children[0]}')
            else:
                self._load(left)

            if right.loc is None:
                self._code(f'sbc #{right.children[0]}')
            else:
                self._code(f'sbc ${hex(right.loc)[2:]}')

        self._setloc(t, Reg.A)

    def add(self, t):
        left, right = t.children

        self._code('clc')

        # if left operand is already in A, add the right
        if left.loc is Reg.A:
            # if right is an immediate
            if right.loc is None:
                # just add it
                self._code(f'adc #{right.children[0]}')
            else:
                # load it from zero-page
                self._code(f'adc ${hex(right.loc)[2:]}')

        # if right operand is already in A, add the left
        elif right.loc is Reg.A:
            # if left is an immediate
            if left.loc is None:
                # just add it
                self._code(f'adc #{left.children[0]}')
            else:
                # load it from zero-page
                self._code(f'adc ${hex(left.loc)[2:]}')

        else:
            self._save_a()
            if left.loc is None:
                self._code(f'lda #{left.children[0]}')
            else:
                self._load(left)

            if right.loc is None:
                self._code(f'adc #{right.children[0]}')
            else:
                self._code(f'adc ${hex(right.loc)[2:]}')

        self._setloc(t, Reg.A)

    def imm(self, t):
        self._setloc(t, None)

    def _save_a(self):
        t = self.registers.get(Reg.A)
        if t is not None:
            for i in self.addrtable:
                if self.addrtable[i] is None:
                    t.loc = i
                    self.addrtable[i] = t
                    addr = hex(i)[2:]
                    self._code(f'sta ${addr}')
                    break

    def _load(self, t):
        addr = hex(t.loc)[2:]
        self._code(f'lda ${addr}')

    def _setloc(self, t, loc):
        setattr(t, 'loc', loc)
        if loc in Reg:
            self.registers[loc] = t

    def _code(self, code):
        self.prg.code.append(code)


PASSES = [
    (VarsChecker, True),
    (CodeGenerator, False),
]


def compile(ast):
    prg = Program()

    for cls, top_down in PASSES:
        v = cls(prg)
        if top_down:
            v.visit_topdown(ast)
        else:
            v.visit(ast)


    return '\n'.join(prg.code)
