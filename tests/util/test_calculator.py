import pytest

# Calculator function
def calculator(math_expression):
    result = eval(math_expression)
    return result


# Tests of calculator function


def test_calculatorSum():
    assert calculator("1 + 2") == 3


def test_calculator_sum2():
    assert calculator("5 + 3") == 8


def test_calculator_sub():
    assert calculator("5 - 3") == 2


def test_calculator_sub2():
    assert calculator("20 - 30") == -10


def test_calculator_mul():
    assert calculator("20 * 30") == 600


def test_calculator_mul2():
    assert calculator("7 * 9") == 63


def test_calculator_div():
    assert calculator("90 / 10") == 9


def test_calculator_div2():
    assert calculator("55 / 5") == 11
