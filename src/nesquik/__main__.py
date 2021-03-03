import logging

import click
from lark import logger

from nesquik.compiler import compile
from nesquik.parser import parse


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
@click.option('--org', type=AddrType(), required=False, default=0xc000,
    help='Program start address')
def nq(file, out, org):
    code = file.read()
    print(code)

    ast = parse(code)
    print(ast.pretty())

    program = compile(ast, org)
    print('\n'.join(program.asm))

    print()
    for byte in program.obj:
        print(hex(byte)[2:], end=' ')

    print()
    print(f'size: {len(program.obj)} bytes')

    if out:
        out.write(program.obj)


if __name__ == '__main__':
    nq()  # pylint: disable=no-value-for-parameter
