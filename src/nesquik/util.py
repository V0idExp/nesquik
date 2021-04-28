import colorama as color

from nesquik.ir_generator import TAC, Assignment, BinOp, Branch, Goto, Label, Return, Location


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


def _fmt_branch(tac):
    return (
        _fmt_padding(tac) +
        color.Fore.YELLOW + color.Style.BRIGHT + f'{tac.op.value}' + color.Style.RESET_ALL +
        f' {tac.first} ' +
        color.Fore.YELLOW + color.Style.BRIGHT + f'jmp' + color.Style.RESET_ALL +
        color.Style.DIM + color.Fore.GREEN + f' {_fmt_value(tac.dst)}')


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
    Assignment: _fmt_assignment,
    BinOp: _fmt_binop,
    Branch: _fmt_branch,
    Goto: _fmt_goto,
    Label: _fmt_label,
    Return: _fmt_return,
}


def print_ir(ir_code: [TAC]):
    """
    Pretty-print IR code sequence.
    """
    for tac in ir_code:
        formatted = _FORMATTERS[type(tac)](tac)
        print(formatted + color.Style.RESET_ALL)
