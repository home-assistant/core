"""Test NextBus util functions."""

from typing import Any

import pytest

from homeassistant.components.nextbus.util import listify, maybe_first


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        ("foo", ["foo"]),
        (["foo"], ["foo"]),
        (None, []),
    ],
)
def test_listify(input: Any, expected: list[Any]) -> None:
    """Test input listification."""
    assert listify(input) == expected


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        ([], []),
        (None, None),
        ("test", "test"),
        (["test"], "test"),
        (["test", "second"], "test"),
    ],
)
def test_maybe_first(input: list[Any] | None, expected: Any) -> None:
    """Test maybe getting the first thing from a list."""
    assert maybe_first(input) == expected
