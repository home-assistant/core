"""Test inputs."""

import pytest

from homeassistant.util.yaml import (
    Input,
    UndefinedSubstitution,
    extract_inputs,
    substitute,
)


def test_extract_inputs() -> None:
    """Test extracting inputs from data."""
    assert extract_inputs(Input("hello")) == {"hello"}
    assert extract_inputs({"info": [1, Input("hello"), 2, Input("world")]}) == {
        "hello",
        "world",
    }


def test_substitute() -> None:
    """Test we can substitute."""
    assert substitute(Input("hello"), {"hello": 5}) == 5

    with pytest.raises(UndefinedSubstitution):
        substitute(Input("hello"), {})

    assert substitute(
        {"info": [1, Input("hello"), 2, Input("world")]},
        {"hello": 5, "world": 10},
    ) == {"info": [1, 5, 2, 10]}
