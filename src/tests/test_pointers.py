import pytest


pytestmark = pytest.mark.skip('Refactoring')


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
    assert cpu.y == 6


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
    assert cpu.y == 6


DEREF_LOCAL_PTR_TO_GLOBAL_VAR = '''
var a = 10

func main():
    var *c = &a
    return *c
'''

def test_deref_local_ptr_to_global_var(cpu):
    cpu.compile_and_run(DEREF_LOCAL_PTR_TO_GLOBAL_VAR)
    assert cpu.y == 10


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
    assert cpu.y == exp_result


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
    assert cpu.y == exp_result
    assert cpu.memory[cpu.zp_offset] == 0


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
    assert cpu.y == exp_result


ASSIGN_TO_GLOBAL_VIA_PTR = '''
var a = 200

func main():
    var *ptr = &a
    *ptr = 123
    return a
'''
def test_assign_to_global_via_ptr(cpu):
    cpu.compile_and_run(ASSIGN_TO_GLOBAL_VIA_PTR)
    assert cpu.y == 123


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
    assert cpu.y == 10


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
    assert cpu.y == 40


PTRS_TO_EXPLICIT_ADDRESS = '''
func main():
    var *ppu = $2000
    *ppu = 111
'''

def test_ptrs_to_explicit_address(cpu):
    cpu.compile_and_run(PTRS_TO_EXPLICIT_ADDRESS)
    assert cpu.memory[0x2000] == 111


PTR_AS_ARRAY_INDEXING = '''
var a = 5
var b = 6
var c = 7

func main():
    var *arr = &a
    return arr[1] + arr[2]  # b + c
'''

def test_ptr_as_array_indexing(cpu):
    cpu.compile_and_run(PTR_AS_ARRAY_INDEXING)
    assert cpu.y == 13


PTR_AS_ARRAY_INDEXING_ITER = '''
var a = 5
var b = 6
var c = 7
var d = 8

func main():
    var acc = 0
    var *values = &a
    var i = 0
    while i < 4:
        acc = acc + values[i]
        i = i + 1
    return acc
'''

def test_ptr_as_array_indexing_iter(cpu):
    cpu.compile_and_run(PTR_AS_ARRAY_INDEXING_ITER)
    assert cpu.y == 26


PTR_AS_ARRAY_STACK_VALUES = '''
func main():
    var a = 5
    var b = 6
    var c = 7
    var d = 8
    var i = 0
    var acc = 0
    var *stack_values = &d  # stack grows down, last value as pivot
    while i < 4:
        acc = acc + stack_values[i]
        i = i + 1
    return acc
'''
def test_ptr_as_array_stack_values(cpu):
    cpu.compile_and_run(PTR_AS_ARRAY_STACK_VALUES)
    assert cpu.y == 26


PTR_AS_ARRAY_INDEXED_ASSIGNING = '''
var *mem = $10
var i = 0
func main():
    while i < 4:
        mem[i] = 5 + i
        i = i + 1
'''
def test_ptr_as_array_indexed_assigning(cpu):
    cpu.compile_and_run(PTR_AS_ARRAY_INDEXED_ASSIGNING)
    assert sum(cpu.memory[0x10:0x14]) == 26


PTR_AS_ARRAY_TEMPS_IN_INDEX_EXPR = '''
var *mem = $10
func main():
    mem[1] = 4
    mem[mem[1] - 3] = $aa
'''
def test_ptr_as_array_temps_in_index_expr(cpu):
    cpu.compile_and_run(PTR_AS_ARRAY_TEMPS_IN_INDEX_EXPR)
    assert cpu.memory[0x11] == 0xaa


ZERO_PAGE_ARRAYS = '''
var arr1[5]
var arr2[5]
var *ptr = arr2

func main():
    ptr[0] = 7
    arr2[1] = 8
    ptr[2] = 9
'''
def test_zero_page_arrays(cpu):
    cpu.compile_and_run(ZERO_PAGE_ARRAYS)
    first_addr = cpu.zp_offset
    second_addr = first_addr + 5
    assert cpu.memory[second_addr] == 7
    assert cpu.memory[second_addr + 1] == 8
    assert cpu.memory[second_addr + 2] == 9


STACK_ARRAYS = '''
func main():
    var arr1[5]
    var arr2[5]
    var *ptr = arr2
    arr1[0] = 3
    arr2[0] = 2
    ptr[1] = 1
'''
def test_stack_arrays(cpu):
    cpu.compile_and_run(STACK_ARRAYS)
    assert cpu.memory[0x1f8] == 3
    assert cpu.memory[0x1f3] == 2
    assert cpu.memory[0x1f4] == 1
