import pytest


@pytest.mark.parametrize('code, exp_result', [
    (
        'a = 2 + 3\n'
        'b = 4 + 5\n'
        'return a + b',
        14,
    ),
    (
        'a = 2 + 2\n'
        'b = 6 - a\n'
        'c = a * b\n'
        'return c * 2 - b',
        14,
    ),
])
def test_vars(cpu, code, exp_result):
    cpu.compile_and_run(code)
    assert cpu.a == exp_result
