import pytest


@pytest.mark.parametrize('code, exp_result', [
    ('return $f0', 240),
    ('return 2 + 2', 4),
    ('return 5 + 4 + 3 + 2 + 1', 15),
    ('return 5 + 2 - 1', 6),
    ('return 5 - (2 + 2)', 1),
    ('return 10 - 3 - 2 - 1', 4),
    # ('return -5', 251),
    # ('return -5 + 20 + (-$a)', 5),
    # ('return -2 - 3 - 5 - -20', 10),
    # ('return (-2) + (-8)', 246),
    # ('return 2 + 2 * 2', 6),
    # ('return 2 * 3 - 2 + 3', 7),
    # ('return -3 * 2 + 3 * 3', 3),
    # ('return -3 * (2 + 3) * 3', 211),
    # ('return (2 + 3) * (4 + 5)', 45),
    # ('return 8 / 2', 4),
    # ('return 8 / 3', 2),
    # ('return (13 / 2) * (8 / 3)', 12),
    # ('return 4 / 5', 0),
    # ('return 5 != 6', 1),
    # ('return 5 < 6', 1),
    # ('return 5 <= 6', 1),
    # ('return 5 == 6', 0),
    # ('return 5 > 6', 0),
    # ('return 5 >= 6', 0),
    # ('return 6 != 5', 1),
    # ('return 6 > 5', 1),
    # ('return 6 >= 5', 1),
    # ('return 6 == 5', 0),
    # ('return 6 <= 5', 0),
    # ('return 6 < 5', 0),
    # ('return ((2 == 2) + (0 == (3 > 3))) == 2', 1)
])
def test_expressions(cpu, code, exp_result):
    main_wrapper = f'func main():\n\t{code}\n'
    cpu.compile_and_run(main_wrapper)
    assert cpu.y == exp_result
