import pytest

@pytest.mark.parametrize('code, exp_result', [
    (
        'return $f0',
        240,
    ),
    (
        'return -5',
        251,
    ),
    (
        'return 5 + 2 - 1',
        6
    ),
    (
        'return 5 - (2 + 2)',
        1,
    ),
    (
        'return -5 + 20 + (-$a)',
        5,
    ),
    (
        'return -2 - 3 - 5 - -20',
        10,
    ),
    (
        'return (-2) + (-8)',
        246,
    )
])
def test_add_sub(cpu, code, exp_result):
    cpu.compile_and_run(code)
    assert cpu.a == exp_result
