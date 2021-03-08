import pytest

GLOBAL_PTRS_TO_GLOBAL_VARS = '''
var a = 5
var b = 4
var c = 3

var *p_a = $6
var *p_b = $7
var *p_c = $8

func main():
    return (*p_a + *p_b) - *p_c
'''

def test_global_ptrs_to_global_vars(cpu):
    cpu.compile_and_run(GLOBAL_PTRS_TO_GLOBAL_VARS)
    assert cpu.a == 6


PTR_AS_VALUE_IN_EXPRESSIONS = '''
var *a = 5
var *b = 4
var *c = 3

func main():
    return (a + b) - c
'''

def test_ptr_as_value_in_expressions(cpu):
    cpu.compile_and_run(PTR_AS_VALUE_IN_EXPRESSIONS)
    assert cpu.a == 6


DEREF_LOCAL_PTR_TO_GLOBAL_VAR = '''
var a = 10

func main():
    var *c = $6  # address of `a`
    return *c
'''

def test_deref_local_ptr_to_global_var(cpu):
    cpu.compile_and_run(DEREF_LOCAL_PTR_TO_GLOBAL_VAR)
    assert cpu.a == 10


DEREF_PTR_ARITHMETICS = '''
var a = 111
var b = 123
var c = 222

func main():
    var *c = ${addr}
    c = c + {offset}
    return *c
'''

@pytest.mark.parametrize('addr,offset,exp_result', [
    (0x06, 1, 123),
    (0x08, -2, 111),
    (0x07, 0, 123),
    (0x06, 2, 222),
])
def test_deref_ptr_arithmetics(cpu, addr, offset, exp_result):
    cpu.compile_and_run(DEREF_PTR_ARITHMETICS.format(addr=addr, offset=offset))
    assert cpu.a == exp_result


DEREF_PTR_IN_LOOP_EXPR = '''
var a = 25

func main():
    # pointer to `a`
    var *ptr = $6
    var i = 0

    while *ptr > (4 - 4):       # this creates temps on stack
        *ptr = *ptr - (25 / 5)  # as well as this
        i = i + (2 - 1)         # and this

    return i
'''

@pytest.mark.parametrize('code,exp_result', [
    (DEREF_PTR_IN_LOOP_EXPR, 5),
])
def test_deref_ptr_in_loop_expr(cpu, code, exp_result):
    cpu.compile_and_run(code)
    assert cpu.a == exp_result
    assert cpu.memory[0x06] == 0


DEREF_PTR_IN_EXPRESSIONS = '''
var a = 5
var b = 4
var c = 3

func main():
    var *ptr_a = $6
    var *ptr_b = $7
    var *ptr_c = $8

    return {expr}
'''

@pytest.mark.parametrize('expr,exp_result', [
    ('(*ptr_c + *ptr_b) - (*ptr_a)', 2),
    ('(*ptr_b + *ptr_c) - (*ptr_a)', 2),
    ('*ptr_b - *ptr_c + *ptr_a', 6),
    ('(*ptr_b + *ptr_a) / *ptr_c', 3),
    ('(*ptr_a * *ptr_b + 1) / *ptr_c', 7),
    ('*ptr_a > *ptr_b', 1),
    ('*ptr_a >= *ptr_b', 1),
    ('*ptr_b == *ptr_a', 0),
    ('*ptr_a == *ptr_b', 0),
    ('*ptr_c < *ptr_b', 1),
    ('*ptr_c <= *ptr_b', 1),
    ('*ptr_c != *ptr_b', 1),
    ('*ptr_b == *ptr_b', 1),
])
def test_deref_ptr_in_expressions(cpu, expr, exp_result):
    cpu.compile_and_run(DEREF_PTR_IN_EXPRESSIONS.format(expr=expr))
    assert cpu.a == exp_result


ASSIGN_TO_MEMORY = '''
var a = 200

func main():
    var *ptr = $6
    *ptr = 123
    return a
'''
def test_assign_to_memory(cpu):
    cpu.compile_and_run(ASSIGN_TO_MEMORY)
    assert cpu.a == 123
