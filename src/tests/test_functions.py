import pytest

SIMPLE_FUNCS = '''
var a = 5
var b = $14

func foo():
    return a + 5

func bar():
    return b

func main():
    return foo() + bar()
'''

def test_simple_funcs(cpu):
    cpu.compile_and_run(SIMPLE_FUNCS)
    assert cpu.a == 30


FUNCS_WITH_LOCALS = '''
var a = {a}
var b = {b}

# dumb on purpose, to trash some locals on the stack :)
func max():
    var result = 0
    var first = a
    var second = b
    var tmp
    if first >= second:
        # just to create some temporaries on stack
        tmp = (second + first) - (first + second)
        result = first
    else:
        result = second
    return result

func main():
    return max()
'''

@pytest.mark.parametrize('a,b', [
    (21, 201),
    (100, 0),
    (255, 255),
    (-21, -4),
])
def test_funcs_with_locals(cpu, a, b):
    code = FUNCS_WITH_LOCALS.format(a=a, b=b)
    cpu.compile_and_run(code)
    exp_result = max(a, b)
    if exp_result < 0:
        exp_result += 256
    assert cpu.a == exp_result


FUNCS_WITH_GLOBALS_SHADOWING = '''
var a = 5
var b = 10

func foo():
    # initialize local `b` using the value of the global in an expression
    var b = b + 5
    # local `b` shadows the global
    a = b

func bar():
    # initialize local `a` with value of the global
    var a = a

    # initialize local `b`
    var b = 130

    # changes do not affect the global `a`
    a = a + 5

    # `a` and `b` shadow their global counterparts
    return a + b

func main():
    foo()  # ... global `a` is now 15

    return bar()
'''

def test_funcs_with_globals_shadowing(cpu):
    cpu.compile_and_run(FUNCS_WITH_GLOBALS_SHADOWING)
    assert cpu.a == 150
    assert cpu.memory[0x06] == 15  # check global `a`
    assert cpu.memory[0x07] == 10  # check global `b`
