"""Test the limited size dictionary."""

from collections.abc import Callable
from typing import Any

import pytest

from homeassistant.util.limited_size_dict import LimitedSizeDict


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        pytest.param(lambda d: d.copy(), {"b": 2, "c": 3}, id="copy"),
        pytest.param(lambda d: d | {"d": 4}, {"c": 3, "d": 4}, id="or"),
        pytest.param(lambda d: {"d": 4} | d, {"b": 2, "c": 3}, id="ror"),
    ],
)
def test_new_dict_keeps_size_limit(
    operation: Callable[[LimitedSizeDict[str, int]], Any], expected: dict[str, int]
) -> None:
    """Test operations returning a new dict keep the size limit."""
    data = LimitedSizeDict({"a": 1, "b": 2, "c": 3}, size_limit=2)

    result = operation(data)

    assert type(result) is LimitedSizeDict
    assert result.size_limit == 2
    assert list(result.items()) == list(expected.items())
    result["e"] = 5
    assert len(result) == 2
