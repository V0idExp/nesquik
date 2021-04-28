import colorama as color

from nesquik.ir_generator import TAC, Assignment, BinOp, Branch, Goto, Label


def _fmt_padding(tac):
    fg = color.Style.DIM + color.Fore.GREEN
    return fg + f'{tac.label}:\t' if tac.label else '\t' + color.Fore.RESET


def _fmt_assignment(tac):
    return _fmt_padding(tac) + ' '.join(filter(
        lambda v: bool(v),
        [
            f'{tac.dst} =',
            color.Fore.YELLOW + color.Style.BRIGHT + tac.op.value + color.Style.RESET_ALL,
            str(tac.first) if tac.first is not None else '',
            str(tac.second) if tac.second is not None else '',
        ]))


def _fmt_binop(tac):
    return _fmt_padding(tac) +  f'{tac.dst} = {tac.first} {tac.op.value} {tac.second}'


def _fmt_branch(tac):
    return (
        _fmt_padding(tac) +
        color.Fore.YELLOW + color.Style.BRIGHT + f'{tac.op.value}' + color.Style.RESET_ALL +
        f' {tac.first} ' +
        color.Fore.YELLOW + color.Style.BRIGHT + f'goto' + color.Style.RESET_ALL +
        color.Style.DIM + color.Fore.GREEN + f' {tac.dst}')


def _fmt_goto(tac):
    return (
        _fmt_padding(tac) +
        color.Fore.YELLOW + color.Style.BRIGHT +
        f'{tac.op.value} ' +
        color.Style.RESET_ALL +
        tac.dst)


def _fmt_label(tac):
    return _fmt_padding(tac)


_FORMATTERS = {
    Assignment: _fmt_assignment,
    BinOp: _fmt_binop,
    Branch: _fmt_branch,
    Goto: _fmt_goto,
    Label: _fmt_label,
}


def print_ir(ir_code: [TAC]):
    """
    Pretty-print IR code sequence.
    """
    for tac in ir_code:
        formatted = _FORMATTERS[type(tac)](tac)
        print(formatted + color.Style.RESET_ALL)
