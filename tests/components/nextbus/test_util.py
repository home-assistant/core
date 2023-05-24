"""Test NextBus util functions."""
from typing import Any

import pytest

from homeassistant.components.nextbus.util import invert_dict, listify, maybe_first


def test_invert_dict():
    """Test dictionary inversion."""
    input = {"key": "value"}
    assert invert_dict(input) == {"value": "key"}

    input = {"key": "value", "key2": "value"}
    try:
        invert_dict(input)
        pytest.fail()
    except ValueError:
        pass


@pytest.mark.parametrize(
    ("input", "expected"),
    (
        ("foo", ["foo"]),
        (["foo"], ["foo"]),
        (None, []),
    ),
)
def test_listify(input: Any, expected: list[Any]) -> None:
    """Test input listification."""
    assert listify(input) == expected


@pytest.mark.parametrize(
    ("input", "expected"),
    (
        ([], []),
        (None, None),
        ("test", "test"),
        (["test"], "test"),
    ),
)
def test_maybe_first(input: list[Any], expected: Any) -> None:
    """Test maybe getting the first thing from a list."""
    assert maybe_first(input) == expected
