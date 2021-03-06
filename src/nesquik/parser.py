from pprint import pprint

from lark import Lark
from lark.indenter import Indenter


_grammar = r'''
    start: var_list func_list

    func_list: (func|COMMENT|_NL)*

    func: "func" NAME "(" arg_list ")" ":" _NL _INDENT var_list _statement_list _DEDENT

    arg_list: (arg ("," arg)*)?

    arg: PTRNAME | NAME

    var_list: (_var_decl|COMMENT|_NL)*

    var: (PTRNAME|NAME) ["=" expression]
       | NAME "[" NUMBER "]"            -> array

    _var_decl: "var" var ("," var)*

    _statement_list: (_statement|COMMENT|_NL)*

    _statement: if_stmt
              | while_stmt
              | assign
              | mem_assign
              | index_assign
              | call
              | ret
              | "pass"

    body: _NL _INDENT _statement_list _DEDENT

    while_stmt: "while" expression ":" body

    if_stmt: if_branch elif_branch* else_branch?
    if_branch: "if" expression ":" body
    elif_branch: "elif" expression ":" body
    else_branch: "else" ":" body

    assign: NAME "=" expression

    mem_assign: PTRNAME "=" expression

    index_assign: NAME "[" expression "]" "=" expression

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

    call: NAME "(" (expression ("," expression)*)? ")"

    ?binop: expression "+" term         -> add
          | expression "-" term         -> sub

    ?term: factor "*" term              -> mul
         | factor "/" term              -> div
         | factor

    ?unop: "-" factor                   -> neg

    ?factor: NAME                       -> ref
           | NUMBER                     -> imm
           | "(" expression ")"
           | unop
           | call
           | "*" NAME                   -> deref
           | "&" NAME                   -> getref
           | NAME "[" expression "]"    -> index

    NUMBER: HEXINT | INT

    PTRNAME: "*" NAME

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
