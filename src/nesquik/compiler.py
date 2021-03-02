from lark import Visitor, Transformer, v_args
from enum import Enum


class NESQuikError(Exception):

    def __init__(self, tree, *args):
        super().__init__(*args)
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
        self.addrtable = [None] * 0xff
        self.reserved = 2

    def ret(self, t):
        result = t.children[0]
        if result.loc is None:
            # immediate
            self._code(f'lda #{result.children[0]}')
        elif result.loc is Reg.A:
            # do nothing, result already in A
            pass
        elif result.loc is Reg.X:
            # transfer X to A
            self._code(f'txa')
        elif result.loc is Reg.Y:
            # transfer Y to A
            self._code(f'tya')
        else:
            self._code(f'lda ${result.addr}')

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
                # subtract from zero-page and remove
                self._code(f'sbc ${right.addr}')
                self._free(right)

        else:
            self._pusha()
            self._pulla(left)

            if right.loc is None:
                # immediate
                self._code(f'sbc #{right.children[0]}')
            else:
                # memory
                self._code(f'sbc ${right.addr}')
                self._free(right)

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
                # add it by loading from zero-page
                self._code(f'adc ${right.addr}')
                # remove it from zero-page
                self._free(right)

        # if right operand is already in A, add the left
        elif right.loc is Reg.A:
            if left.loc is None:
                # left is an immediate, just add it
                self._code(f'adc #{left.children[0]}')
            else:
                # load it from zero-page
                self._code(f'adc ${left.addr}')
                # remove it frome zero page
                self._free(left)

        # none of the operands are in A
        else:
            # save A
            self._pusha()

            # load left into A
            self._pulla(left)

            if right.loc is None:
                # immediate
                self._code(f'adc #{right.children[0]}')
            else:
                # memory
                self._code(f'adc ${right.addr}')
                self._free(right)

        self._setloc(t, Reg.A)

    def imm(self, t):
        self._setloc(t, None)

    def neg(self, t):
        arg = t.children[0]
        self._pusha()

        # load arg into A
        self._pulla(arg)

        # perform two's complement negation: invert all bits and add 1
        self._code(f'clc')
        self._code(f'eor #$ff')
        self._code(f'adc #1')

        self._setloc(t, Reg.A)

    def _pusha(self):
        t = self.registers.get(Reg.A)
        if t is not None:
            try:
                i = next(i for i in range(self.reserved, len(self.addrtable)) if self.addrtable[i] is None)
                self._setloc(t, i)
                self._code(f'sta ${t.addr}')
            except StopIteration:
                raise NESQuikInternalError(t, 'out of temporary memory')

    def _pulla(self, t):
        if t.loc is None:
            # immediate
            self._code(f'lda #{t.children[0]}')
        elif isinstance(t.loc, int):
            # memory
            self._code(f'lda ${t.addr}')

        self._setloc(t, Reg.A)

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
        setattr(t, 'addr', f'{hex(loc)[2:]}' if isinstance(loc, int) else None)

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

    return prg.code
