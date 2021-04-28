import pytest


pytestmark = pytest.mark.skip('Refactoring')


WHILE_CODE = '''
func main():
    var i = 0

    while i < 10:
        i = i + 1

    return i
'''

def test_while(cpu):
    cpu.compile_and_run(WHILE_CODE)
    assert cpu.y == 10

WHILE_TRUE = '''
func main():
    while 1:
        pass
'''
def test_while_infinite(cpu):
    cpu.compile(WHILE_TRUE)
    loop_addr = 0xc012
    loops_count = 0
    loop_cycles = 10

    while cpu.pc != loop_addr:
        cpu.step()

    cycles = cpu.processorCycles

    while loops_count < 256:
        cpu.step()
        if cpu.pc == loop_addr:
            loops_count += 1

    elapsed_cycles = cpu.processorCycles - cycles
    assert elapsed_cycles == loop_cycles * 256
