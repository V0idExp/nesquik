import pytest


@pytest.mark.parametrize('code,conditions,exp_results', [
    (
        [
            'var a = 10',
            'if {expr}:',
            '    a = a + 2',
            'return a',
        ],
        ('a == 10', 'a >= 10', 'a <= 10', 'a < 10'),
        (12, 12, 12, 10),
    ),
    (
        [
            'var a = 10',
            'if {expr}:',
            '    a = a + 2',
            'else:',
            '    a = a - 2'
            'return a',
        ],
        ('a == 10', 'a >= 10', 'a <= 10', 'a < 10'),
        (12, 12, 12, 8),
    ),
    (
        [
            'var a = 10',
            'var b = {expr}',
            'var max',
            'if a == b:',
            '    max = a',
            'elif a > b:',
            '    max = a',
            'else:',
            '    max = b',
            'return max',
        ],
        (10, 15, 5),
        (10, 15, 10),
    ),
])
def test_if_elif_else(cpu, code, conditions, exp_results):
    for i, expr in enumerate(conditions):
        cpu.compile_and_run('\n'.join(code).format(expr=expr))
        exp_result = exp_results[i]
        assert cpu.a == exp_result
