import colorama as color

from nesquik.tac import Op, Location, TAC


def _fmt_padding(tac):
    return f'{_fmt_value(tac.label)}:' if tac.label else '\t' + color.Fore.RESET


def _fmt_assignment(tac):
    return _fmt_padding(tac) + ' '.join(filter(
        lambda v: bool(v),
        [
            f'{_fmt_value(tac.dst)} =',
            color.Fore.YELLOW + color.Style.BRIGHT + tac.op.value + color.Style.RESET_ALL,
            str(tac.first) if tac.first is not None else '',
            str(tac.second) if tac.second is not None else '',
        ]))


def _fmt_value(val):
    if val.loc == Location.REGISTER:
        return color.Fore.GREEN + color.Style.BRIGHT + f'%{val.value}' + color.Style.RESET_ALL
    elif val.loc == Location.IMMEDIATE:
        return val.value
    elif val.loc == Location.CODE:
        return color.Fore.CYAN + color.Style.BRIGHT + f'@{val.value}' + color.Style.RESET_ALL
    else:
        raise ValueError(f'unknown value location {val.loc}')


def _fmt_binop(tac):
    return _fmt_padding(tac) +  f'{_fmt_value(tac.dst)} = {_fmt_value(tac.first)} {tac.op.value} {_fmt_value(tac.second)}'


def _fmt_if(tac):
    return (
        _fmt_padding(tac) +
        color.Fore.YELLOW + color.Style.BRIGHT + 'if' + color.Style.RESET_ALL +
        f' {tac.first} ≠ 0' +
        color.Fore.YELLOW + color.Style.BRIGHT + ' → ' + color.Style.RESET_ALL +
        color.Style.DIM + color.Fore.GREEN + _fmt_value(tac.dst))


def _fmt_goto(tac):
    return (
        _fmt_padding(tac) +
        color.Fore.YELLOW + color.Style.BRIGHT +
        f'{tac.op.value} ' +
        color.Style.RESET_ALL +
        _fmt_value(tac.dst))


def _fmt_label(tac):
    return _fmt_padding(tac)


def _fmt_return(tac):
    return (
        _fmt_padding(tac) +
        color.Fore.YELLOW + color.Style.BRIGHT + f'{tac.op.value}' + color.Style.RESET_ALL +
        f' {_fmt_value(tac.first)}')


_FORMATTERS = {
    Op.ADD: _fmt_binop,
    Op.SUB: _fmt_binop,
    Op.DIV: _fmt_binop,
    Op.MUL: _fmt_binop,
    Op.EQ: _fmt_binop,
    Op.NEQ: _fmt_binop,
    Op.GT: _fmt_binop,
    Op.GEQ: _fmt_binop,
    Op.LT: _fmt_binop,
    Op.LEQ: _fmt_binop,
    Op.IF_Z: _fmt_if,
    Op.JMP: _fmt_goto,
    Op.EMPTY: _fmt_label,
    Op.RET: _fmt_return,
}


def print_ir(ir_code: [TAC]):
    """
    Pretty-print IR code sequence.
    """
    for tac in ir_code:
        formatted = _FORMATTERS[tac.op](tac)
        print(formatted + color.Style.RESET_ALL)
