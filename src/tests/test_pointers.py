import pytest

GLOBAL_PTRS_TO_GLOBAL_VARS = '''
var a = 5
var b = 4
var c = 3

var *p_a = &a
var *p_b = &b
var *p_c = &c

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

@pytest.mark.skip(reason='need 16 bit arithmetics')
def test_ptr_as_value_in_expressions(cpu):
    cpu.compile_and_run(PTR_AS_VALUE_IN_EXPRESSIONS)
    assert cpu.a == 6


DEREF_LOCAL_PTR_TO_GLOBAL_VAR = '''
var a = 10

func main():
    var *c = &a
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
    var *c = &{var}
    c = c + {offset}
    return *c
'''

@pytest.mark.skip(reason='need 16 bit arithmetics')
@pytest.mark.parametrize('var,offset,exp_result', [
    ('a', 1, 123),
    ('c', -2, 111),
    ('b', 0, 123),
    ('a', 2, 222),
])
def test_deref_ptr_arithmetics(cpu, var, offset, exp_result):
    cpu.compile_and_run(DEREF_PTR_ARITHMETICS.format(var=var, offset=offset))
    assert cpu.a == exp_result


DEREF_PTR_IN_LOOP_EXPR = '''
var a = 25

func main():
    var *ptr = &a
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
    var *ptr_a = &a
    var *ptr_b = &b
    var *ptr_c = &c

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


ASSIGN_TO_GLOBAL_VIA_PTR = '''
var a = 200

func main():
    var *ptr = &a
    *ptr = 123
    return a
'''
def test_assign_to_global_via_ptr(cpu):
    cpu.compile_and_run(ASSIGN_TO_GLOBAL_VIA_PTR)
    assert cpu.a == 123


LOCAL_PTRS_TO_LOCAL_VARS = '''
func main():
    var a = 5
    var *ptr_a = &a
    var b
    var *ptr_b = &b
    *ptr_b = *ptr_a * 2
    return b
'''

def test_local_ptrs_to_local_vars(cpu):
    cpu.compile_and_run(LOCAL_PTRS_TO_LOCAL_VARS)
    assert cpu.a == 10


PTR_ASSIGNMENT = '''
var a = 10
var b = 20
var c = 30

func main():
    var *ptr1 = &a
    var *ptr2 = &b
    var *ptr3 = &c

    ptr2 = ptr3
    ptr3 = ptr1

    return *ptr2 + *ptr3  # c + a
'''

def test_ptr_assignment(cpu):
    cpu.compile_and_run(PTR_ASSIGNMENT)
    assert cpu.a == 40


PTRS_TO_EXPLICIT_ADDRESS = '''
func main():
    var *ppu = $2000
    *ppu = 111
'''

def test_ptrs_to_explicit_address(cpu):
    cpu.compile_and_run(PTRS_TO_EXPLICIT_ADDRESS)
    assert cpu.memory[0x2000] == 111
