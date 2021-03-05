from pprint import pprint

from lark import Lark
from lark.indenter import Indenter


_grammar = r'''
    start: _var_list _statement_list

    _var_list: (_var_decl|COMMENT|_NL)*

    var: NAME ["=" expression]

    _var_decl: "var" var ("," var)*

    _statement_list: (_statement|COMMENT|_NL)*

    _statement: if_stmt
              | assign
              | ret

    _block: _NL _INDENT _statement_list _DEDENT

    if_stmt: if_branch elif_branch* else_branch?
    if_branch: "if" expression ":" _block
    elif_branch: "elif" expression ":" _block
    else_branch: "else" ":" _block

    assign: NAME "=" expression

    ret: "return" expression

    ?expression: term
               | cmp
               | binop

    ?cmp: expression ">" expression     -> gt
        | expression ">=" expression    -> geq
        | expression "<" expression     -> lt
        | expression "<=" expression    -> leq
        | expression "==" expression    -> eq
        | expression "!=" expression    -> neq

    ?binop: expression "+" term         -> add
          | expression "-" term         -> sub

    ?term: factor "*" term              -> mul
         | factor "/" term              -> div
         | factor

    ?unop: "-" factor                   -> neg

    ?factor: NAME                       -> ref
           | HEXINT                     -> imm
           | INT                        -> imm
           | "(" expression ")"
           | unop

    HEXINT: "$" HEXDIGIT+

    _NL: /(\r?\n[\t ]*)+/

    %import common.CNAME -> NAME
    %import common.INT
    %import common.WS_INLINE
    %import common.HEXDIGIT
    %import common.SH_COMMENT -> COMMENT

    %ignore WS_INLINE
    %ignore COMMENT

    %declare _INDENT
    %declare _DEDENT
'''


class TreeIndenter(Indenter):

    NL_type = '_NL'
    OPEN_PAREN_types = []
    CLOSE_PAREN_types = []
    INDENT_type = '_INDENT'
    DEDENT_type = '_DEDENT'
    tab_len = 4


_parser = Lark(_grammar, parser='lalr', propagate_positions=True, postlex=TreeIndenter(), debug=True)


def parse(code, transforms=None):
    ast = _parser.parse(code)

    for cls in transforms or []:
        t = cls()
        ast = t.transform(ast)

    return ast
