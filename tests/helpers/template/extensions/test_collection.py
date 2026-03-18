"""Test collection extension."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template


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
    assert (
        template.Template("{{ value is list }}", hass).async_render({"value": value})
        == expected
    )


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
    assert (
        template.Template("{{ value is set }}", hass).async_render({"value": value})
        == expected
    )


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
    assert (
        template.Template("{{ value is tuple }}", hass).async_render({"value": value})
        == expected
    )


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
        template.Template("{{ set(value) }}", hass).async_render({"value": value})
        == list(expected.values())[0]
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
    result = template.Template("{{ tuple(value) }}", hass).async_render(
        {"value": value}
    )
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
        template.Template("{{ zip(cola, colb) | list }}", hass).async_render(
            {"cola": cola, "colb": colb}
        )
        == expected
    )
    assert (
        template.Template(
            "[{% for a, b in zip(cola, colb) %}({{a}}, {{b}}), {% endfor %}]", hass
        ).async_render({"cola": cola, "colb": colb})
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
    assert (
        template.Template("{{ zip(*col) | list }}", hass).async_render({"col": col})
        == expected
    )
    assert (
        template.Template(
            "{% set a, b = zip(*col) %}[{{a}}, {{b}}]", hass
        ).async_render({"col": col})
        == expected
    )


def test_shuffle(hass: HomeAssistant) -> None:
    """Test shuffle."""
    # Test basic shuffle
    result = template.Template("{{ shuffle([1, 2, 3, 4, 5]) }}", hass).async_render()
    assert len(result) == 5
    assert set(result) == {1, 2, 3, 4, 5}

    # Test shuffle with seed
    result1 = template.Template(
        "{{ shuffle([1, 2, 3, 4, 5], seed=42) }}", hass
    ).async_render()
    result2 = template.Template(
        "{{ shuffle([1, 2, 3, 4, 5], seed=42) }}", hass
    ).async_render()
    assert result1 == result2  # Same seed should give same result

    # Test shuffle with different seed
    result3 = template.Template(
        "{{ shuffle([1, 2, 3, 4, 5], seed=123) }}", hass
    ).async_render()
    # Different seeds should usually give different results
    # (but we can't guarantee it for small lists)
    assert len(result3) == 5
    assert set(result3) == {1, 2, 3, 4, 5}


def test_flatten(hass: HomeAssistant) -> None:
    """Test flatten."""
    # Test basic flattening
    assert template.Template(
        "{{ flatten([[1, 2], [3, 4]]) }}", hass
    ).async_render() == [1, 2, 3, 4]

    # Test nested flattening
    assert template.Template(
        "{{ flatten([[[1, 2], [3, 4]], [[5, 6], [7, 8]]]) }}", hass
    ).async_render() == [1, 2, 3, 4, 5, 6, 7, 8]

    # Test flattening with levels
    assert template.Template(
        "{{ flatten([[[1, 2], [3, 4]], [[5, 6], [7, 8]]], levels=1) }}", hass
    ).async_render() == [[1, 2], [3, 4], [5, 6], [7, 8]]

    # Test mixed types
    assert template.Template(
        "{{ flatten([[1, 'a'], [2, 'b']]) }}", hass
    ).async_render() == [1, "a", 2, "b"]

    # Test empty list
    assert template.Template("{{ flatten([]) }}", hass).async_render() == []

    # Test single level
    assert template.Template("{{ flatten([1, 2, 3]) }}", hass).async_render() == [
        1,
        2,
        3,
    ]


def test_intersect(hass: HomeAssistant) -> None:
    """Test intersect."""
    # Test basic intersection
    result = template.Template(
        "{{ [1, 2, 3, 4] | intersect([3, 4, 5, 6]) | sort }}", hass
    ).async_render()
    assert result == [3, 4]

    # Test no intersection
    result = template.Template("{{ [1, 2] | intersect([3, 4]) }}", hass).async_render()
    assert result == []

    # Test string intersection
    result = template.Template(
        "{{ ['a', 'b', 'c'] | intersect(['b', 'c', 'd']) | sort }}", hass
    ).async_render()
    assert result == ["b", "c"]

    # Test empty list intersection
    result = template.Template("{{ [] | intersect([1, 2, 3]) }}", hass).async_render()
    assert result == []


def test_difference(hass: HomeAssistant) -> None:
    """Test difference."""
    # Test basic difference
    result = template.Template(
        "{{ [1, 2, 3, 4] | difference([3, 4, 5, 6]) | sort }}", hass
    ).async_render()
    assert result == [1, 2]

    # Test no difference
    result = template.Template(
        "{{ [1, 2] | difference([1, 2, 3, 4]) }}", hass
    ).async_render()
    assert result == []

    # Test string difference
    result = template.Template(
        "{{ ['a', 'b', 'c'] | difference(['b', 'c', 'd']) | sort }}", hass
    ).async_render()
    assert result == ["a"]

    # Test empty list difference
    result = template.Template("{{ [] | difference([1, 2, 3]) }}", hass).async_render()
    assert result == []


def test_union(hass: HomeAssistant) -> None:
    """Test union."""
    # Test basic union
    result = template.Template(
        "{{ [1, 2, 3] | union([3, 4, 5]) | sort }}", hass
    ).async_render()
    assert result == [1, 2, 3, 4, 5]

    # Test string union
    result = template.Template(
        "{{ ['a', 'b'] | union(['b', 'c']) | sort }}", hass
    ).async_render()
    assert result == ["a", "b", "c"]

    # Test empty list union
    result = template.Template(
        "{{ [] | union([1, 2, 3]) | sort }}", hass
    ).async_render()
    assert result == [1, 2, 3]

    # Test duplicate elements
    result = template.Template(
        "{{ [1, 1, 2, 2] | union([2, 2, 3, 3]) | sort }}", hass
    ).async_render()
    assert result == [1, 2, 3]


def test_symmetric_difference(hass: HomeAssistant) -> None:
    """Test symmetric_difference."""
    # Test basic symmetric difference
    result = template.Template(
        "{{ [1, 2, 3, 4] | symmetric_difference([3, 4, 5, 6]) | sort }}", hass
    ).async_render()
    assert result == [1, 2, 5, 6]

    # Test no symmetric difference (identical sets)
    result = template.Template(
        "{{ [1, 2, 3] | symmetric_difference([1, 2, 3]) }}", hass
    ).async_render()
    assert result == []

    # Test string symmetric difference
    result = template.Template(
        "{{ ['a', 'b', 'c'] | symmetric_difference(['b', 'c', 'd']) | sort }}", hass
    ).async_render()
    assert result == ["a", "d"]

    # Test empty list symmetric difference
    result = template.Template(
        "{{ [] | symmetric_difference([1, 2, 3]) | sort }}", hass
    ).async_render()
    assert result == [1, 2, 3]


def test_collection_functions_as_tests(hass: HomeAssistant) -> None:
    """Test that type checking functions work as tests."""
    # Test various type checking functions
    assert template.Template("{{ [1,2,3] is list }}", hass).async_render()
    assert template.Template("{{ set([1,2,3]) is set }}", hass).async_render()
    assert template.Template("{{ (1,2,3) is tuple }}", hass).async_render()


def test_collection_error_handling(hass: HomeAssistant) -> None:
    """Test error handling in collection functions."""

    # Test flatten with non-iterable
    with pytest.raises(TemplateError, match="flatten expected a list"):
        template.Template("{{ flatten(123) }}", hass).async_render()

    # Test intersect with non-iterable
    with pytest.raises(TemplateError, match="intersect expected a list"):
        template.Template("{{ [1, 2] | intersect(123) }}", hass).async_render()

    # Test difference with non-iterable
    with pytest.raises(TemplateError, match="difference expected a list"):
        template.Template("{{ [1, 2] | difference(123) }}", hass).async_render()

    # Test shuffle with no arguments
    with pytest.raises(TemplateError, match="shuffle expected at least 1 argument"):
        template.Template("{{ shuffle() }}", hass).async_render()
