"""Test collection extension."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError

from tests.helpers.template.helpers import render


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2, 3], True),
        ({"a": 1}, False),
        ({1, 2, 3}, False),
        ((1, 2, 3), False),
        ("abc", False),
        ("", False),
        (5, False),
        (None, False),
        ({"foo": "bar", "baz": "qux"}, False),
    ],
)
def test_is_list(hass: HomeAssistant, value: Any, expected: bool) -> None:
    """Test list test."""
    assert render(hass, "{{ value is list }}", {"value": value}) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2, 3], False),
        ({"a": 1}, False),
        ({1, 2, 3}, True),
        ((1, 2, 3), False),
        ("abc", False),
        ("", False),
        (5, False),
        (None, False),
        ({"foo": "bar", "baz": "qux"}, False),
    ],
)
def test_is_set(hass: HomeAssistant, value: Any, expected: bool) -> None:
    """Test set test."""
    assert render(hass, "{{ value is set }}", {"value": value}) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2, 3], False),
        ({"a": 1}, False),
        ({1, 2, 3}, False),
        ((1, 2, 3), True),
        ("abc", False),
        ("", False),
        (5, False),
        (None, False),
        ({"foo": "bar", "baz": "qux"}, False),
    ],
)
def test_is_tuple(hass: HomeAssistant, value: Any, expected: bool) -> None:
    """Test tuple test."""
    assert render(hass, "{{ value is tuple }}", {"value": value}) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2, 3], {"expected0": {1, 2, 3}}),
        ({"a": 1}, {"expected1": {"a"}}),
        ({1, 2, 3}, {"expected2": {1, 2, 3}}),
        ((1, 2, 3), {"expected3": {1, 2, 3}}),
        ("abc", {"expected4": {"a", "b", "c"}}),
        ("", {"expected5": set()}),
        (range(3), {"expected6": {0, 1, 2}}),
        ({"foo": "bar", "baz": "qux"}, {"expected7": {"foo", "baz"}}),
    ],
)
def test_set(hass: HomeAssistant, value: Any, expected: bool) -> None:
    """Test set conversion."""
    assert (
        render(hass, "{{ set(value) }}", {"value": value}) == list(expected.values())[0]
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2, 3], {"expected0": (1, 2, 3)}),
        ({"a": 1}, {"expected1": ("a",)}),
        ({1, 2, 3}, {"expected2": (1, 2, 3)}),  # Note: set order is not guaranteed
        ((1, 2, 3), {"expected3": (1, 2, 3)}),
        ("abc", {"expected4": ("a", "b", "c")}),
        ("", {"expected5": ()}),
        (range(3), {"expected6": (0, 1, 2)}),
        ({"foo": "bar", "baz": "qux"}, {"expected7": ("foo", "baz")}),
    ],
)
def test_tuple(hass: HomeAssistant, value: Any, expected: bool) -> None:
    """Test tuple conversion."""
    result = render(hass, "{{ tuple(value) }}", {"value": value})
    expected_value = list(expected.values())[0]
    if isinstance(value, set):  # Sets don't have predictable order
        assert set(result) == set(expected_value)
    else:
        assert result == expected_value


@pytest.mark.parametrize(
    ("cola", "colb", "expected"),
    [
        ([1, 2], [3, 4], [(1, 3), (2, 4)]),
        ([1, 2], [3, 4, 5], [(1, 3), (2, 4)]),
        ([1, 2, 3, 4], [3, 4], [(1, 3), (2, 4)]),
    ],
)
def test_zip(hass: HomeAssistant, cola, colb, expected) -> None:
    """Test zip."""
    assert (
        render(hass, "{{ zip(cola, colb) | list }}", {"cola": cola, "colb": colb})
        == expected
    )
    assert (
        render(
            hass,
            "[{% for a, b in zip(cola, colb) %}({{a}}, {{b}}), {% endfor %}]",
            {"cola": cola, "colb": colb},
        )
        == expected
    )


@pytest.mark.parametrize(
    ("col", "expected"),
    [
        ([(1, 3), (2, 4)], [(1, 2), (3, 4)]),
        (["ax", "by", "cz"], [("a", "b", "c"), ("x", "y", "z")]),
    ],
)
def test_unzip(hass: HomeAssistant, col, expected) -> None:
    """Test unzipping using zip."""
    assert render(hass, "{{ zip(*col) | list }}", {"col": col}) == expected
    assert (
        render(hass, "{% set a, b = zip(*col) %}[{{a}}, {{b}}]", {"col": col})
        == expected
    )


def test_shuffle(hass: HomeAssistant) -> None:
    """Test shuffle."""
    # Test basic shuffle
    result = render(hass, "{{ shuffle([1, 2, 3, 4, 5]) }}")
    assert len(result) == 5
    assert set(result) == {1, 2, 3, 4, 5}

    # Test shuffle with seed
    result1 = render(hass, "{{ shuffle([1, 2, 3, 4, 5], seed=42) }}")
    result2 = render(hass, "{{ shuffle([1, 2, 3, 4, 5], seed=42) }}")
    assert result1 == result2  # Same seed should give same result

    # Test shuffle with different seed
    result3 = render(hass, "{{ shuffle([1, 2, 3, 4, 5], seed=123) }}")
    # Different seeds should usually give different results
    # (but we can't guarantee it for small lists)
    assert len(result3) == 5
    assert set(result3) == {1, 2, 3, 4, 5}


def test_flatten(hass: HomeAssistant) -> None:
    """Test flatten."""
    # Test basic flattening
    assert render(hass, "{{ flatten([[1, 2], [3, 4]]) }}") == [1, 2, 3, 4]

    # Test nested flattening
    assert render(hass, "{{ flatten([[[1, 2], [3, 4]], [[5, 6], [7, 8]]]) }}") == [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
    ]

    # Test flattening with levels
    assert render(
        hass, "{{ flatten([[[1, 2], [3, 4]], [[5, 6], [7, 8]]], levels=1) }}"
    ) == [[1, 2], [3, 4], [5, 6], [7, 8]]

    # Test mixed types
    assert render(hass, "{{ flatten([[1, 'a'], [2, 'b']]) }}") == [1, "a", 2, "b"]

    # Test empty list
    assert render(hass, "{{ flatten([]) }}") == []

    # Test single level
    assert render(hass, "{{ flatten([1, 2, 3]) }}") == [
        1,
        2,
        3,
    ]


def test_intersect(hass: HomeAssistant) -> None:
    """Test intersect."""
    # Test basic intersection
    result = render(hass, "{{ [1, 2, 3, 4] | intersect([3, 4, 5, 6]) | sort }}")
    assert result == [3, 4]

    # Test no intersection
    result = render(hass, "{{ [1, 2] | intersect([3, 4]) }}")
    assert result == []

    # Test string intersection
    result = render(hass, "{{ ['a', 'b', 'c'] | intersect(['b', 'c', 'd']) | sort }}")
    assert result == ["b", "c"]

    # Test empty list intersection
    result = render(hass, "{{ [] | intersect([1, 2, 3]) }}")
    assert result == []


def test_difference(hass: HomeAssistant) -> None:
    """Test difference."""
    # Test basic difference
    result = render(hass, "{{ [1, 2, 3, 4] | difference([3, 4, 5, 6]) | sort }}")
    assert result == [1, 2]

    # Test no difference
    result = render(hass, "{{ [1, 2] | difference([1, 2, 3, 4]) }}")
    assert result == []

    # Test string difference
    result = render(hass, "{{ ['a', 'b', 'c'] | difference(['b', 'c', 'd']) | sort }}")
    assert result == ["a"]

    # Test empty list difference
    result = render(hass, "{{ [] | difference([1, 2, 3]) }}")
    assert result == []


def test_union(hass: HomeAssistant) -> None:
    """Test union."""
    # Test basic union
    result = render(hass, "{{ [1, 2, 3] | union([3, 4, 5]) | sort }}")
    assert result == [1, 2, 3, 4, 5]

    # Test string union
    result = render(hass, "{{ ['a', 'b'] | union(['b', 'c']) | sort }}")
    assert result == ["a", "b", "c"]

    # Test empty list union
    result = render(hass, "{{ [] | union([1, 2, 3]) | sort }}")
    assert result == [1, 2, 3]

    # Test duplicate elements
    result = render(hass, "{{ [1, 1, 2, 2] | union([2, 2, 3, 3]) | sort }}")
    assert result == [1, 2, 3]


def test_symmetric_difference(hass: HomeAssistant) -> None:
    """Test symmetric_difference."""
    # Test basic symmetric difference
    result = render(
        hass, "{{ [1, 2, 3, 4] | symmetric_difference([3, 4, 5, 6]) | sort }}"
    )
    assert result == [1, 2, 5, 6]

    # Test no symmetric difference (identical sets)
    result = render(hass, "{{ [1, 2, 3] | symmetric_difference([1, 2, 3]) }}")
    assert result == []

    # Test string symmetric difference
    result = render(
        hass, "{{ ['a', 'b', 'c'] | symmetric_difference(['b', 'c', 'd']) | sort }}"
    )
    assert result == ["a", "d"]

    # Test empty list symmetric difference
    result = render(hass, "{{ [] | symmetric_difference([1, 2, 3]) | sort }}")
    assert result == [1, 2, 3]


def test_collection_functions_as_tests(hass: HomeAssistant) -> None:
    """Test that type checking functions work as tests."""
    # Test various type checking functions
    assert render(hass, "{{ [1,2,3] is list }}")
    assert render(hass, "{{ set([1,2,3]) is set }}")
    assert render(hass, "{{ (1,2,3) is tuple }}")


def test_collection_error_handling(hass: HomeAssistant) -> None:
    """Test error handling in collection functions."""

    # Test flatten with non-iterable
    with pytest.raises(TemplateError, match="flatten expected a list"):
        render(hass, "{{ flatten(123) }}")

    # Test intersect with non-iterable
    with pytest.raises(TemplateError, match="intersect expected a list"):
        render(hass, "{{ [1, 2] | intersect(123) }}")

    # Test difference with non-iterable
    with pytest.raises(TemplateError, match="difference expected a list"):
        render(hass, "{{ [1, 2] | difference(123) }}")

    # Test shuffle with no arguments
    with pytest.raises(TemplateError, match="shuffle expected at least 1 argument"):
        render(hass, "{{ shuffle() }}")
