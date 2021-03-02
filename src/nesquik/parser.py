from pprint import pprint
from lark import Lark


_grammar = r'''
    start: (_statement|COMMENT|NEWLINE)*

    _statement: assign
              | ret

    assign: NAME "=" expression

    ret: "return" expression

    ?expression: term | binop

    ?binop: expression "+" term -> add
          | expression "-" term -> sub

    ?term: factor "*" term      -> mul
         | factor "/" term      -> div
         | factor

    ?unop: "-" factor           -> neg

    ?factor: NAME               -> ref
           | HEXINT             -> imm
           | INT                -> imm
           | "(" expression ")"
           | unop

    HEXINT: "$" HEXDIGIT+

    %import common.CNAME -> NAME
    %import common.INT
    %import common.WS_INLINE
    %import common.NEWLINE
    %import common.HEXDIGIT
    %import common.SH_COMMENT -> COMMENT

    %ignore WS_INLINE
    %ignore COMMENT
'''


_parser = Lark(_grammar, parser='lalr', propagate_positions=True)


def parse(code, transforms=None):
    ast = _parser.parse(code)

    for cls in transforms or []:
        t = cls()
        ast = t.transform(ast)

    return ast
