import pytest
from nesquik.compiler import NESQuikUndefinedVariable


@pytest.mark.parametrize('code, exp_result', [
    (
        'var a = 2 + 3\n'
        'var b = 4 + 5\n'
        'func main():\n'
        '    return a + b\n',
        14,
    ),
    (
        'var a = 2 + 2\n'
        'var b = 6 - a\n'
        'var c = a * b\n'
        'func main():\n'
        '    return c * 2 - b\n',
        14,
    ),
    (
        'var a = 5\n'
        'var b = 23 / a\n'
        'var c = 14 / 15\n'
        'func main():\n'
        '    return a * b - -(a / 5)\n',
        21,
    ),
    (
        'var a = 5\n'
        'var b = a * 5\n'
        'func main():\n'
        '    a = b\n'
        '    return a\n',
        25,
    ),
    (
        'var a = 5\n'
        'var b = 6\n'
        'func main():\n'
        '    return (a + (a == a)) == b\n',
        1,
    ),
    (
        'var a = 5\n'
        'var b = 6\n'
        'func main():\n'
        '    return a > b\n',
        0,
    ),
    (
        'var a = 5\n'
        'var b = 6\n'
        'func main():\n'
        '    return a < b\n',
        1,
    ),
    (
        'var a = 5\n'
        'var b = 6\n'
        'func main():\n'
        '    return a == b\n',
        0,
    ),
    (
        'var a = 5\n'
        'var b = 6\n'
        'func main():\n'
        '    return a <= b\n',
        1,
    ),
    (
        'var a = 5\n'
        'var b = 6\n'
        'func main():\n'
        '    return b >= a\n',
        1,
    )
])
def test_vars(cpu, code, exp_result):
    cpu.compile_and_run(code)
    assert cpu.y == exp_result


@pytest.mark.parametrize('code', [
    'var a = 5\n'
    'var b = a + c\n'
    'func main():\n'
    '   return 0',

    'var c = d\n'
    'func main():\n'
    '   return 0',

    'func main():\n'
    '   return a',
])
def test_undefined_vars(cpu, code):
    with pytest.raises(NESQuikUndefinedVariable):
        cpu.compile_and_run(code)
