from enum import Enum

from lark import Visitor

from nesquik.opcodes import OPCODES, AddrMode, Op


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

    def __init__(self, _):
        self.registers = {}
        self.addrtable = [None] * 0xff
        self.reserved = 2

    def ret(self, t):
        self._pulla(t, t.children[0])

    def sub(self, t):
        self._instr(t, Op.SEC)
        left, right = t.children

        # if left operand is already in A, subtract the right
        if left.loc is Reg.A:
            self._instr(t, Op.SBC, right)
            self._free(right)
        else:
            self._pusha()
            self._pulla(t, left)
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
            self._pusha()
            self._pulla(t, left)
            self._instr(t, Op.ADC, right)
            self._free(right)

        self._setloc(t, Reg.A)

    def imm(self, t):
        self._setloc(t, None)

    def neg(self, t):
        arg = t.children[0]
        self._pusha()

        # load arg into A
        self._pulla(t, arg)

        # perform two's complement negation: invert all bits and add 1
        self._instr(t, Op.CLC)
        self._instr(t, Op.EOR, 0xff)
        self._instr(t, Op.ADC, 0x01)

        self._setloc(t, Reg.A)

    def _pusha(self):
        t = self.registers.get(Reg.A)
        if t is not None:
            try:
                i = next(i for i in range(self.reserved, len(self.addrtable)) if self.addrtable[i] is None)
                self._setloc(t, i)
                self._instr(t, Op.STA, t)
            except StopIteration:
                raise NESQuikInternalError(t, 'out of temporary memory')

    def _pulla(self, t, arg):
        if arg.loc is Reg.A:
            # do nothing
            return
        elif arg.loc is Reg.X:
            # transfer X to A
            self._instr(t, Op.TXA)
        elif arg.loc is Reg.Y:
            # transfer Y to A
            self._instr(t, Op.TYA)
        else:
            # either immediate or memory
            self._instr(t, Op.LDA, arg)
        self._setloc(arg, Reg.A)

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

    def _instr(self, t, op, arg=None):
        if arg is None:
            mode = AddrMode.Implied
        elif isinstance(arg, (int, str)):
            mode = AddrMode.Immediate
        elif arg.loc is None:
            mode = AddrMode.Immediate
            arg = str(arg.children[0])
        elif isinstance(arg.loc, int):
            mode = AddrMode.Zeropage
            arg = arg.loc
        else:
            raise NESQuikInternalError(t, 'cannot determine address mode')

        code = getattr(t, 'code', [])
        code.append((op, mode, arg))
        setattr(t, 'code', code)


class Assembler(Visitor):

    def __init__(self, prg):
        self.prg = prg
        self.size = 0

    def __default__(self, t):
        for op, mode, arg in getattr(t, 'code', []):
            if mode is AddrMode.Implied:
                code = op.value
            elif mode is AddrMode.Immediate:
                code = f'{op.value} #{arg}'
                if isinstance(arg, str):
                    if arg.startswith('$'):
                        arg = int(arg[1:], base=16)
                    else:
                        arg = int(arg, base=10)
            elif mode is AddrMode.Zeropage:
                code = f'{op.value} ${arg}'

            opcode, size = OPCODES[(op, mode)]
            bytecode = bytearray(size)
            bytecode[0] = opcode
            if size == 2:
                bytecode[1] = arg
            elif size > 2:
                raise NESQuikInternalError(t, 'unsupported operand size')

            self.prg.asm.append(code)
            self.prg.obj.extend(bytecode)


PASSES = [
    (VarsChecker, True),
    (CodeGenerator, False),
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
