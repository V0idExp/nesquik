import pytest


@pytest.mark.parametrize('code,conditions,exp_results', [
    (
        [
            'var a = 10',
            'if {expr}:',
            '    a = a + 2',
            'return a',
        ],
        ('a == 10', 'a >= 10', 'a <= 10', 'a < 10', '10 == a', '10 <= a', '10 >= a', '10 > a'),
        (12, 12, 12, 10, 12, 12, 12, 10),
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
    (
        [
            'var a = 5',
            'if {expr}:',
            '    a = (5 + 4) - (3 + 2 + 1)',
            'else:',
            '    a = (2 + 2) + 1',
            'return a',
        ],
        ('a > 5', 'a == 5'),
        (5, 3),
    ),
])
def test_if_elif_else(cpu, code, conditions, exp_results):
    for i, expr in enumerate(conditions):
        cpu.compile_and_run('\n'.join(code).format(expr=expr))
        exp_result = exp_results[i]
        assert cpu.a == exp_result


NESTED_IF_ELIF_TEST_CODE = '''
var a = {a_val}
if a > 5:
    if a > (30 - 15):
        # truncate to 15
        a = (5 + 4) - (3 + 2 + 1) + (6 * 2)
    elif a > 10:
        # truncate to 10
        a = 20 + (-5 * 2)
    else:
        # truncate to 5
        a = 2 + 3
else:
    a = 3 - (4 / 2)
return a
'''

@pytest.mark.parametrize('a_val,result', [
    (20, 15),
    (13, 10),
    (6, 5),
    (5, 1),
])
def test_if_elif_else_nested(cpu, a_val, result):
    code = NESTED_IF_ELIF_TEST_CODE.format(a_val=a_val)
    cpu.compile_and_run(code)
    assert cpu.a == result
