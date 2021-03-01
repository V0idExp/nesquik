import logging

import click
from lark import logger
from nesquik.parser import parse
from nesquik.compiler import compile

logger.setLevel(logging.DEBUG)


@click.command()
@click.argument('file', type=click.File('r'))
def nq(file):
    ast = parse(file.read())
    print(ast.pretty())

    code = compile(ast)
    print(code)


if __name__ == '__main__':
    nq()  # pylint: disable=no-value-for-parameter
