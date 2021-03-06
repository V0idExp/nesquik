FOO_BAR_CODE = '''
var a = 5

func foo():
    return a + 3

func bar():
    return 2

func main():
    return foo() + bar()
'''


def test_foo_bar(cpu):
    cpu.compile_and_run(FOO_BAR_CODE)
    assert cpu.a == 0x0a
