from pprint import pprint
import lark


_grammar = r'''
    ?start: (_statement|COMMENT|NEWLINE)*

    _statement: assign
              | ret

    assign: NAME "=" expression

    ret: "return" expression

    ?expression: term | binop

    ?binop: expression "+" term -> add
          | expression "-" term -> sub

    ?term: factor "*" factor    -> mul
         | factor "/" factor    -> div
         | factor

    ?factor: NAME        -> ref
           | HEXINT      -> imm
           | INT         -> imm
           | "(" expression ")"

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


class Node:

    def __init__(self, *children):
        self.children = children

    def pretty_print(self):
        nodes = [(0, self)]
        while nodes:
            level, node = nodes.pop(0)
            print('  ' * level + str(node))
            for child in reversed(node.children):
                nodes.insert(0, (level + 1, child))

    def __str__(self):
        return f'{self.__class__.__name__}'


_parser = lark.Lark(_grammar, parser='lalr', propagate_positions=True)


def parse(code):
    return _parser.parse(code)
