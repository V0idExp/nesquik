import pytest
from nesquik.compiler import NESQuikUndefinedVariable

@pytest.mark.parametrize('code, exp_result', [
    (
        '''
        a = 2 + 3
        b = 4 + 5
        return a + b
        ''',
        14,
    ),
    (
        '''
        a = 2 + 2
        b = 6 - a
        c = a * b
        return c * 2 - b
        ''',
        14,
    ),
    (
        '''
        a = 5
        b = 23 / a
        c = 14 / 15
        return a * b - -(a / 5)
        ''',
        21,
    ),
    (
        '''
        a = 5
        b = a * 5
        a = b
        return a
        ''',
        25,
    ),
])
def test_vars(cpu, code, exp_result):
    cpu.compile_and_run(code)
    assert cpu.a == exp_result


@pytest.mark.parametrize('code', [
    '''
    a = 5
    b = a + c
    ''',
    '''
    c = d
    ''',
])
def test_undefined_vars(cpu, code):
    with pytest.raises(NESQuikUndefinedVariable):
        cpu.compile_and_run(code)
