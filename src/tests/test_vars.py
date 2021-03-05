import pytest
from nesquik.compiler import NESQuikUndefinedVariable


@pytest.mark.parametrize('code, exp_result', [
    (
        '''
        var a = 2 + 3
        var b = 4 + 5
        return a + b
        ''',
        14,
    ),
    (
        '''
        var a = 2 + 2
        var b = 6 - a
        var c = a * b
        return c * 2 - b
        ''',
        14,
    ),
    (
        '''
        var a = 5
        var b = 23 / a
        var c = 14 / 15
        return a * b - -(a / 5)
        ''',
        21,
    ),
    (
        '''
        var a = 5
        var b = a * 5
        a = b
        return a
        ''',
        25,
    ),
])
def test_vars(cpu, code, exp_result):
    code = '\n'.join(line.strip() for line in code.split('\n'))
    cpu.compile_and_run(code)
    assert cpu.a == exp_result


@pytest.mark.parametrize('code', [
    '''
    var a = 5
    var b = a + c
    ''',

    '''
    var c = d
    ''',

    '''
    return a
    ''',
])
def test_undefined_vars(cpu, code):
    code = '\n'.join(line.strip() for line in code.split('\n'))
    with pytest.raises(NESQuikUndefinedVariable):
        cpu.compile_and_run(code)


@pytest.mark.parametrize('code', [
    '''
    var a = 1
    a = a + 2
    var b = 3
    ''',
])
def test_unallowed_vars_after_statements(cpu, code):
    with pytest.raises(Exception):
        cpu.compile_and_run(code)
