from enum import Enum


class Op(Enum):
    LDA = 'lda'
    STA = 'sta'
    ADC = 'adc'
    SBC = 'sbc'
    SEC = 'sec'
    CLC = 'clc'
    EOR = 'eor'
    TXA = 'txa'
    TYA = 'tya'


class AddrMode(Enum):
    Immediate = 'imm'
    Implied = 'imp'
    Zeropage = 'zpg'


OPCODES = {
#   Op       Address mode           Code   Size
    (Op.LDA, AddrMode.Immediate):   (0xA9, 2),
    (Op.LDA, AddrMode.Zeropage):    (0xA5, 2),
    (Op.STA, AddrMode.Zeropage):    (0x85, 2),

    (Op.ADC, AddrMode.Immediate):   (0x69, 2),
    (Op.ADC, AddrMode.Zeropage):    (0x65, 2),

    (Op.SBC, AddrMode.Immediate):   (0xE9, 2),
    (Op.SBC, AddrMode.Zeropage):    (0xE5, 2),

    (Op.SEC, AddrMode.Implied):     (0x38, 1),
    (Op.CLC, AddrMode.Implied):     (0x18, 1),

    (Op.EOR, AddrMode.Immediate):   (0x49, 2),

    (Op.TXA, AddrMode.Implied):     (0x8A, 1),
    (Op.TYA, AddrMode.Implied):     (0x98, 1),
}
