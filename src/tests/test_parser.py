from nesquik.parser import parse


def test_expressions():
    code = '2+$0c'
    tree = parse(code)
    assert tree
