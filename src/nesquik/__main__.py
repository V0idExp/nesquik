import logging

import click
import colorama
from lark import logger

from nesquik.classes import Program
from nesquik.ir_generator import IRGenerator
from nesquik.parser import Parser
from nesquik.util import print_ir
from nesquik import target_6502


logger.setLevel(logging.DEBUG)


class AddrType(click.ParamType):

    name = "address"

    def convert(self, value, param, ctx):
        try:
            if value[:2].lower() == '0x':
                return int(value[2:], base=16)
            return int(value, base=10)
        except (TypeError, ValueError):
            self.fail(
                f'expected an address in decimal or hexadecimal format, '
                f'got {value}')


@click.command()
@click.argument('file', type=click.File('r'))
@click.option('-o', '--out', type=click.File('wb'), required=False,
    help='Output binary file name')
@click.option('--org', type=AddrType(), required=False, default='0xc000',
    help='Program start address')
def nq(file, out, org):
    code = file.read()
    prg = Program(code, org)

    stages = [
        Parser,
        IRGenerator,
        target_6502.AsmGenerator,
        target_6502.ObjGenerator,
    ]

    for cls in stages:
        stage = cls()
        stage.exec(prg)

    print(prg.ast.pretty())


    print_ir(prg.ir)

    print('\n'.join(prg.asm))

    print()
    for byte in prg.obj:
        print(hex(byte)[2:], end=' ')

    print()
    print(f'size: {len(prg.obj)} bytes')

    if out:
        out.write(prg.obj)


if __name__ == '__main__':
    colorama.init()
    nq()  # pylint: disable=no-value-for-parameter
