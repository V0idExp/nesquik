import re
from collections import namedtuple

from nesquik.opcodes import Op

LABEL_DEF = re.compile(r'^(?P<id>@\w+):')


Subroutine = namedtuple('Subroutine', ('name', 'code'))


def parse_instructions(code):
    instructions = []
    for line in code.split('\n'):
        line = line.strip().lower()
        if not line:
            continue

        label = None

        mo = LABEL_DEF.search(line)
        if mo is not None:
            label = mo.group('id')
            line = LABEL_DEF.sub('', line).strip()

        line = line.split()
        op = Op(line[0])
        arg = line[1] if len(line) == 2 else None
        instructions.append((op, arg, label))

    return instructions


# Multiplication subroutine.
# X - first operand
# Y - second operand
# A - result
MUL = Subroutine(
    name='MUL',
    code=parse_instructions('''
        lda #$00
        sta $00
    @0: tya
        and #$01
        beq @1
        txa
        clc
        adc $00
        sta $00
    @1: txa
        asl
        tax
        tya
        lsr
        tay
        bne @0
        lda $00
        rts
    '''))


# Division subroutine.
# $0 - dividend
# $1 - divisor
# A  - result
#
# http://6502org.wikidot.com/software-math-intdiv
DIV = Subroutine(
    name='DIV',
    code=parse_instructions('''
        lda #0
        ldx #8
        asl $0
    @0: rol
        cmp $1
        bcc @1
        sbc $1
    @1: rol $0
        dex
        bne @0
        lda $0
        rts
    '''))
