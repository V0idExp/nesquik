from enum import Enum, unique


@unique
class Op(Enum):
    ADC = 'adc'
    AND = 'and'
    ASL = 'asl'
    BCC = 'bcc'
    BCS = 'bcs'
    BEQ = 'beq'
    BNE = 'bne'
    BRK = 'brk'
    CLC = 'clc'
    CMP = 'cmp'
    DEX = 'dex'
    EOR = 'eor'
    INC = 'inc'
    INY = 'iny'
    INX = 'inx'
    JMP = 'jmp'
    JSR = 'jsr'
    LDA = 'lda'
    LDX = 'ldx'
    LDY = 'ldy'
    LSR = 'lsr'
    PHA = 'pha'
    PLA = 'pla'
    ROL = 'rol'
    RTS = 'rts'
    SBC = 'sbc'
    SEC = 'sec'
    STA = 'sta'
    STX = 'stx'
    STY = 'sty'
    TAX = 'tax'
    TAY = 'tay'
    TSX = 'tsx'
    TXA = 'txa'
    TXS = 'txs'
    TYA = 'tya'


class AddrMode(Enum):
    Immediate = 'imm'
    Implied = 'imp'
    Zeropage = 'zp'
    Absolute = 'abs'
    Relative = 'rel'
    IndirectY = 'iny'


OPCODES = {
#    Op      Address mode            Code  Size
    (Op.ADC, AddrMode.Immediate):   (0x69, 2),
    (Op.ADC, AddrMode.IndirectY):   (0x71, 2),
    (Op.ADC, AddrMode.Zeropage):    (0x65, 2),
    (Op.AND, AddrMode.Immediate):   (0x29, 2),
    (Op.AND, AddrMode.Zeropage):    (0x25, 2),
    (Op.ASL, AddrMode.Implied):     (0x0A, 1),
    (Op.ASL, AddrMode.Zeropage):    (0x06, 2),
    (Op.BCC, AddrMode.Relative):    (0x90, 2),
    (Op.BCS, AddrMode.Relative):    (0xB0, 2),
    (Op.BEQ, AddrMode.Relative):    (0xF0, 2),
    (Op.BNE, AddrMode.Relative):    (0xD0, 2),
    (Op.BRK, AddrMode.Implied):     (0x00, 1),
    (Op.CLC, AddrMode.Implied):     (0x18, 1),
    (Op.CMP, AddrMode.Immediate):   (0xC9, 2),
    (Op.CMP, AddrMode.IndirectY):   (0xD1, 2),
    (Op.CMP, AddrMode.Zeropage):    (0xC5, 2),
    (Op.DEX, AddrMode.Implied):     (0xCA, 1),
    (Op.EOR, AddrMode.Immediate):   (0x49, 2),
    (Op.INC, AddrMode.Zeropage):    (0xE6, 2),
    (Op.INY, AddrMode.Implied):     (0xC8, 1),
    (Op.INX, AddrMode.Implied):     (0xE8, 1),
    (Op.JMP, AddrMode.Absolute):    (0x4C, 3),
    (Op.JSR, AddrMode.Absolute):    (0x20, 3),
    (Op.LDA, AddrMode.Immediate):   (0xA9, 2),
    (Op.LDA, AddrMode.IndirectY):   (0xB1, 2),
    (Op.LDA, AddrMode.Zeropage):    (0xA5, 2),
    (Op.LDX, AddrMode.Immediate):   (0xA2, 2),
    (Op.LDX, AddrMode.Zeropage):    (0xA6, 2),
    (Op.LDY, AddrMode.Immediate):   (0xA0, 2),
    (Op.LDY, AddrMode.Zeropage):    (0xA4, 2),
    (Op.LSR, AddrMode.Implied):     (0x4A, 1),
    (Op.LSR, AddrMode.Zeropage):    (0x46, 2),
    (Op.PHA, AddrMode.Implied):     (0x48, 1),
    (Op.PLA, AddrMode.Implied):     (0x68, 1),
    (Op.ROL, AddrMode.Implied):     (0x2A, 1),
    (Op.ROL, AddrMode.Zeropage):    (0x26, 2),
    (Op.RTS, AddrMode.Implied):     (0x60, 1),
    (Op.SBC, AddrMode.Immediate):   (0xE9, 2),
    (Op.SBC, AddrMode.IndirectY):   (0xF1, 2),
    (Op.SBC, AddrMode.Zeropage):    (0xE5, 2),
    (Op.SEC, AddrMode.Implied):     (0x38, 1),
    (Op.STA, AddrMode.Zeropage):    (0x85, 2),
    (Op.STX, AddrMode.Zeropage):    (0x86, 2),
    (Op.STY, AddrMode.Zeropage):    (0x84, 2),
    (Op.TAX, AddrMode.Implied):     (0xAA, 1),
    (Op.TAY, AddrMode.Implied):     (0xA8, 1),
    (Op.TSX, AddrMode.Implied):     (0xBA, 1),
    (Op.TXA, AddrMode.Implied):     (0x8A, 1),
    (Op.TXS, AddrMode.Implied):     (0x9A, 1),
    (Op.TYA, AddrMode.Implied):     (0x98, 1),
}


# just a check, lost once few hours because of duplicate opcodes...
_opcodes = [opcode for opcode, _ in OPCODES.values()]
if len(_opcodes) != len(set(_opcodes)):
    raise RuntimeError('!!!DUPLICATE OPCODES!!!')
