import pytest


DEREF_PTR_TO_GLOBAL = '''
var a = 10

func main():
    var *c = $6  # address of `a`
    return *c
'''

def test_deref_ptr_to_global(cpu):
    cpu.compile_and_run(DEREF_PTR_TO_GLOBAL)
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
def test_deref_global_ptr_arithmetics(cpu, addr, offset, exp_result):
    cpu.compile_and_run(DEREF_PTR_ARITHMETICS.format(addr=addr, offset=offset))
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
