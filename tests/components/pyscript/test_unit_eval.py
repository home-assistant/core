"""Unit tests for Python interpreter."""
import asyncio

from homeassistant.components.pyscript.eval import AstEval
import homeassistant.components.pyscript.handler as handler
import homeassistant.components.pyscript.state as state

evalTests = [
    ["1", 1],
    ["1+1", 2],
    ["1+2*3-2", 5],
    ["1-1", 0],
    ["4/2", 2],
    ["4**2", 16],
    ["4<<2", 16],
    ["16>>2", 4],
    ["18 ^ 2", 16],
    ["16 | 2", 18],
    ["0x37 & 0x6c ", 0x24],
    ["11 // 2", 5],
    ["not True", False],
    ["not False", True],
    ["z = 1+2+3; a = z + 1; a + 3", 10],
    ["z = 1+2+3; a = z + 1; a - 3", 4],
    ["x = 1; -x", -1],
    ["z = 5; +z", 5],
    ["~0xff", -256],
    ["x = 1; x < 2", 1],
    ["x = 1; x <= 1", 1],
    ["x = 1; 0 < x < 2", 1],
    ["x = 1; 2 > x > 0", 1],
    ["x = 1; 2 > x >= 1", 1],
    ["x = 1; 0 < x < 2 < -x", 0],
    ["x = [1,2,3]; del x[1:2]; x", [1, 3]],
    ["x = [1,2,3]; del x[1::]; x", [1]],
    ["1 and 2", 2],
    ["1 and 0", 0],
    ["0 or 1", 1],
    ["0 or 0", 0],
    ["f'{1} {2:02d} {3:.1f}'", "1 02 3.0"],
    [["x = None", "x is None"], True],
    ["None is not None", False],
    ["10 in {5, 9, 10, 20}", True],
    ["10 not in {5, 9, 10, 20}", False],
    ["sym_local + 10", 20],
    ["z = 'foo'; z + 'bar'", "foobar"],
    ["xyz.y = 5; xyz.y = 2 + int(xyz.y); int(xyz.y)", 7],
    ["xyz.y = 'bar'; xyz.y += '2'; xyz.y", "bar2"],
    ["z = 'abcd'; z.find('c')", 2],
    ["'abcd'.upper().lower().upper()", "ABCD"],
    ["len('abcd')", 4],
    ["6 if 1-1 else 2", 2],
    ["x = 1; x += 3; x", 4],
    ["z = [1,2,3]; [z[1], z[-1]]", [2, 3]],
    ["'{1} {0}'.format('one', 'two')", "two one"],
    ["'%d, %d' % (23, 45)", "23, 45"],
    ["args = [1, 5, 10]; {6, *args, 15}", {1, 5, 6, 10, 15}],
    ["args = [1, 5, 10]; [6, *args, 15]", [6, 1, 5, 10, 15]],
    ["kw = {'x': 1, 'y': 5}; {**kw}", {"x": 1, "y": 5}],
    [
        "kw = {'x': 1, 'y': 5}; kw2 = {'z': 10}; {**kw, **kw2}",
        {"x": 1, "y": 5, "z": 10},
    ],
    ["[*iter([1, 2, 3])]", [1, 2, 3]],
    ["{*iter([1, 2, 3])}", {1, 2, 3}],
    ["if 1: x = 10\nelse: x = 20\nx", 10],
    ["if 0: x = 10\nelse: x = 20\nx", 20],
    ["i = 0\nwhile i < 5: i += 1\ni", 5],
    ["i = 0\nwhile i < 5: i += 2\ni", 6],
    ["i = 0\nwhile i < 5:\n    i += 1\n    if i == 3: break\n2 * i", 6],
    [
        "i = 0; k = 10\nwhile i < 5:\n    i += 1\n    if i <= 2: continue\n    k += 1\nk + i",
        18,
    ],
    ["i = 1; break; i = 1/0", None],
    ["s = 0;\nfor i in range(5):\n    s += i\ns", 10],
    ["s = 0;\nfor i in iter([10,20,30]):\n    s += i\ns", 60],
    [
        "z = {'foo': 'bar', 'foo2': 12}; z['foo'] = 'bar2'; z",
        {"foo": "bar2", "foo2": 12},
    ],
    ["z = {'foo': 'bar', 'foo2': 12}; z['foo'] = 'bar2'; z.keys()", {"foo", "foo2"}],
    ["z = {'foo', 'bar', 12}; z", {"foo", "bar", 12}],
    [
        "x = dict(key1 = 'value1', key2 = 'value2'); x",
        {"key1": "value1", "key2": "value2"},
    ],
    [
        "x = dict(key1 = 'value1', key2 = 'value2', key3 = 'value3'); del x['key1']; x",
        {"key2": "value2", "key3": "value3"},
    ],
    [
        "x = dict(key1 = 'value1', key2 = 'value2', key3 = 'value3'); del x[['key1', 'key2']]; x",
        {"key3": "value3"},
    ],
    ["z = {'foo', 'bar', 12}; z.remove(12); z.add(20); z", {"foo", "bar", 20}],
    ["z = [0, 1, 2, 3, 4, 5, 6]; z[1:5:2] = [4, 5]; z", [0, 4, 2, 5, 4, 5, 6]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][1:5:2]", [1, 3]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][1:5]", [1, 2, 3, 4]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][1::3]", [1, 4, 7]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][4::]", [4, 5, 6, 7, 8]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][4:]", [4, 5, 6, 7, 8]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][:6:2]", [0, 2, 4]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][:4:]", [0, 1, 2, 3]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][::2]", [0, 2, 4, 6, 8]],
    ["[0, 1, 2, 3, 4, 5, 6, 7, 8][::]", [0, 1, 2, 3, 4, 5, 6, 7, 8]],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[1:5:2] = [6, 8]; z",
        [0, 6, 2, 8, 4, 5, 6, 7, 8],
    ],
    ["z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[1:5] = [10, 11]; z", [0, 10, 11, 5, 6, 7, 8]],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[1::3] = [10, 11, 12]; z",
        [0, 10, 2, 3, 11, 5, 6, 12, 8],
    ],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[4::] = [10, 11, 12, 13]; z",
        [0, 1, 2, 3, 10, 11, 12, 13],
    ],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[4:] = [10, 11, 12, 13, 14]; z",
        [0, 1, 2, 3, 10, 11, 12, 13, 14],
    ],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[:6:2] = [10, 11, 12]; z",
        [10, 1, 11, 3, 12, 5, 6, 7, 8],
    ],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[:4:] = [10, 11, 12, 13]; z",
        [10, 11, 12, 13, 4, 5, 6, 7, 8],
    ],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[::2] = [10, 11, 12, 13, 14]; z",
        [10, 1, 11, 3, 12, 5, 13, 7, 14],
    ],
    [
        "z = [0, 1, 2, 3, 4, 5, 6, 7, 8]; z[::] = [10, 11, 12, 13, 14, 15, 16, 17]; z",
        [10, 11, 12, 13, 14, 15, 16, 17],
    ],
    ["import random as rand, math as m\n[rand.uniform(10,10), m.sqrt(1024)]", [10, 32]],
    ["import cmath\ncmath.sqrt(complex(3, 4))", 2 + 1j],
    ["from math import sqrt as sqroot\nsqroot(1024)", 32],
    [
        """
bar = 100
def foo(bar=6):
    bar += 2
    return bar
    bar += 5
    return 1000
[foo(), foo(5), bar]
""",
        [8, 7, 100],
    ],
    [
        """
bar = 100
def foo(bar=6):
    bar += 2
    del bar
    return bar
    bar += 5
    return 1000
[foo(), foo(5), bar]
""",
        [100, 100, 100],
    ],
    [
        """
bar = 100
bar2 = 1000
bar3 = 100
def foo(arg=6):
    global bar, bar2, bar3
    bar += arg
    bar2 = 1001
    del bar3
    return bar
    bar += arg
    return 1000
[foo(), foo(5), bar, bar2]
""",
        [106, 111, 111, 1001],
    ],
    [
        """
bar = 100
bar2 = 1000
bar3 = 100
def foo(arg=6):
    nonlocal bar, bar2, bar3
    bar += arg
    bar2 = 1001
    del bar3
    return bar
    bar += arg
    return 1000
[foo(), foo(5), bar, bar2]
""",
        [106, 111, 111, 1001],
    ],
    [
        """
@dec_test("abc")
def foo(cnt=4):
    sum = 0
    for i in range(cnt):
        sum += i
        if i == 6:
            return 1000 + sum
        if i == 7:
            break
    return sum
[foo(3), foo(6), foo(10), foo(20), foo()]
""",
        [
            sum(range(3)),
            sum(range(6)),
            1000 + sum(range(7)),
            1000 + sum(range(7)),
            sum(range(4)),
        ],
    ],
    [
        """
def foo(cnt=5):
    sum = 0
    for i in range(cnt):
        if i == 4:
            continue
        if i == 8:
            break
        sum += i
    return sum
[foo(3), foo(6), foo(10), foo(20), foo()]
""",
        [
            sum(range(3)),
            sum(range(6)) - 4,
            sum(range(9)) - 4 - 8,
            sum(range(9)) - 4 - 8,
            sum(range(5)) - 4,
        ],
    ],
    [
        """
def foo(cnt=5):
    sum = 0
    for i in range(cnt):
        if i == 8:
            break
        sum += i
    else:
        return 1000 + sum
    return sum
[foo(3), foo(6), foo(10), foo(20), foo()]
""",
        [
            sum(range(3)) + 1000,
            sum(range(6)) + 1000,
            sum(range(9)) - 8,
            sum(range(9)) - 8,
            sum(range(5)) + 1000,
        ],
    ],
    [
        """
def foo(cnt=5):
    sum = 0
    i = 0
    while i < cnt:
        if i == 8:
            break
        sum += i
        i += 1
    else:
        return 1000 + sum
    return sum
[foo(3), foo(6), foo(10), foo(20), foo()]
""",
        [
            sum(range(3)) + 1000,
            sum(range(6)) + 1000,
            sum(range(9)) - 8,
            sum(range(9)) - 8,
            sum(range(5)) + 1000,
        ],
    ],
    [
        """
def foo(cnt):
    sum = 0
    for i in range(cnt):
        sum += i
        if i != 6:
            pass
        else:
            return 1000 + sum
        if i == 7:
            break
    return sum
[foo(3), foo(6), foo(10), foo(20)]
""",
        [sum(range(3)), sum(range(6)), 1000 + sum(range(7)), 1000 + sum(range(7))],
    ],
    [
        """
def foo(cnt):
    sum = 0
    i = 0
    while i < cnt:
        sum += i
        if i != 6:
            pass
        else:
            return 1000 + sum
        if i == 7:
            break
        i += 1
    return sum
[foo(3), foo(6), foo(10), foo(20)]
""",
        [sum(range(3)), sum(range(6)), 1000 + sum(range(7)), 1000 + sum(range(7))],
    ],
    [
        """
def foo(x=30, *args, y = 123, **kwargs):
    return [x, y, args, kwargs]
[foo(a = 10, b = 3), foo(40, 7, 8, 9, a = 10, y = 3), foo(x=42)]
""",
        [
            [30, 123, (), {"a": 10, "b": 3}],
            [40, 3, (7, 8, 9), {"a": 10}],
            [42, 123, (), {}],
        ],
    ],
    [
        """
def foo(*args):
    return [*args]
lst = [6, 10]
[foo(2, 3, 10) + [*lst], [foo(*lst), *lst]]
""",
        [[2, 3, 10, 6, 10], [[6, 10], 6, 10]],
    ],
    [
        """
def foo(arg1=None, **kwargs):
    return [arg1, kwargs]
[foo(), foo(arg1=1), foo(arg2=20), foo(arg1=10, arg2=20), foo(**{'arg2': 30})]
""",
        [
            [None, {}],
            [1, {}],
            [None, {"arg2": 20}],
            [10, {"arg2": 20}],
            [None, {"arg2": 30}],
        ],
    ],
]


async def run_one_test(test_data, state_func, handler_func):
    """Run one interpreter test."""
    source, expect = test_data
    ast = AstEval("test", state_func=state_func, handler_func=handler_func)
    ast.parse(source)
    if ast.get_exception() is not None:
        print(f"Parsing {source} failed: {ast.get_exception()}")
    # print(ast.dump())
    result = await ast.eval({"sym_local": 10})
    assert result == expect


def test_eval(hass):
    """Test interpreter."""
    handler_func = handler.Handler(hass)
    state_func = state.State(hass, handler_func)
    state_func.register_functions()

    for test_data in evalTests:
        asyncio.run(run_one_test(test_data, state_func, handler_func))


evalTestsExceptions = [
    [None, "parsing error compile() arg 1 must be a string, bytes or AST object"],
    ["1+", "syntax error invalid syntax (<unknown>, line 1)"],
    [
        "1+'x'",
        "Exception in <unknown> line 1 column 0: unsupported operand type(s) for +: 'int' and 'str'",
    ],
    ["xx", "Exception in <unknown> line 1 column 0: name 'xx' is not defined"],
    [
        "xx.yy",
        "Exception in <unknown> line 1 column 0: 'EvalName' object has no attribute 'yy'",
    ],
    [
        "del xx",
        "Exception in <unknown> line 1 column 0: name 'xx' is not defined in del",
    ],
    [
        "with None:\n    pass\n",
        "Exception in <unknown> line 1 column 0: test: not implemented ast ast_with",
    ],
    [
        "func1(1)",
        "Exception in <unknown> line 1 column 0: function 'func1' is not callable (got None)",
    ],
    [
        "def func(a):\n    pass\nfunc()",
        "Exception in <unknown> line 3 column 0: func() missing 1 required positional arguments",
    ],
    [
        "def func(a):\n    pass\nfunc(1, 2)",
        "Exception in <unknown> line 3 column 0: func() called with too many positional arguments",
    ],
    [
        "def func(a=1):\n    pass\nfunc(1, a=3)",
        "Exception in <unknown> line 3 column 0: func() got multiple values for argument 'a'",
    ],
    [
        "def func(*a, b):\n    pass\nfunc(1, 2)",
        "Exception in <unknown> line 3 column 0: func() missing required keyword-only arguments",
    ],
    [
        "import asyncio",
        "Exception in <unknown> line 1 column 0: import of asyncio not allowed",
    ],
    [
        "from asyncio import xyz",
        "Exception in <unknown> line 1 column 0: import from asyncio not allowed",
    ],
    [
        """
def func():
    nonlocal x
    x = 1
func()
""",
        "Exception in func(), <unknown> line 4 column 4: can't find nonlocal 'x' for assignment",
    ],
    [
        """
def func():
    nonlocal x
    x += 1
func()
""",
        "Exception in func(), <unknown> line 4 column 4: can't find nonlocal 'x' for assignment",
    ],
    [
        """
def func():
    global x
    return x
func()
""",
        "Exception in func(), <unknown> line 4 column 11: global name 'x' is not defined",
    ],
]


async def run_one_test_exception(test_data, state_func, handler_func):
    """Run one interpreter test that generates an exception."""
    source, expect = test_data
    ast = AstEval("test", state_func=state_func, handler_func=handler_func)
    ast.parse(source)
    exc = ast.get_exception()
    if exc is not None:
        assert exc == expect
        return
    await ast.eval()
    exc = ast.get_exception()
    if exc is not None:
        assert exc == expect
        return
    assert False


def test_eval_exceptions(hass):
    """Test interpreter exceptions."""
    handler_func = handler.Handler(hass)
    state_func = state.State(hass, handler_func)
    state_func.register_functions()

    for test_data in evalTestsExceptions:
        asyncio.run(run_one_test_exception(test_data, state_func, handler_func))
