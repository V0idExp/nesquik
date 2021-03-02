import logging

import click
from lark import logger

from nesquik.compiler import compile
from nesquik.parser import parse

logger.setLevel(logging.DEBUG)


@click.command()
@click.argument('file', type=click.File('r'))
@click.option('-o', type=click.File('wb'), required=False)
def nq(file, o):
    code = file.read()
    print(code)

    ast = parse(code)
    print(ast.pretty())

    program = compile(ast)
    print('\n'.join(program.asm))

    print()
    for byte in program.obj:
        print(hex(byte)[2:], end=' ')

    print()
    print(f'size: {len(program.obj)} bytes')

    if o:
        o.write(program.obj)

if __name__ == '__main__':
    nq()  # pylint: disable=no-value-for-parameter
