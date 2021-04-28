import pytest


pytestmark = pytest.mark.skip('Refactoring')


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
    assert cpu.y == 30


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
    assert cpu.y == exp_result


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
    assert cpu.y == 150
    assert cpu.memory[cpu.zp_offset] == 15      # check global `a`
    assert cpu.memory[cpu.zp_offset + 1] == 10  # check global `b`


FUNCS_WITH_8BIT_ARGS = '''
func sum(a, b):
    return a + b

func main():
    var v1 = 4
    var v2 = 3
    return sum(v1, v2)
'''
def test_funcs_with_8bit_args(cpu):
    cpu.compile_and_run(FUNCS_WITH_8BIT_ARGS)
    assert cpu.y == 7


FUNCS_WITH_PTR_ARGS = '''
func sum_array(*p, size):
    var sum = 0
    var i = 0
    while i < size:
        sum = sum + p[i]
        i = i + 1
    return sum

func main():
    var arr[3]
    arr[0] = 5
    arr[1] = 4
    arr[2] = 3
    return sum_array(arr, 3)

'''
def test_funcs_with_ptr_args(cpu):
    cpu.compile_and_run(FUNCS_WITH_PTR_ARGS)
    assert cpu.y == 12
