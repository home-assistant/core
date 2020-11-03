"""Test placeholders."""
import pytest

from homeassistant.helpers import placeholder
from homeassistant.util.yaml import Placeholder


def test_extract_placeholders():
    """Test extracting placeholders from data."""
    assert placeholder.extract_placeholders(Placeholder("hello")) == {"hello"}
    assert placeholder.extract_placeholders(
        {"info": [1, Placeholder("hello"), 2, Placeholder("world")]}
    ) == {"hello", "world"}


def test_substitute():
    """Test we can substitute."""
    assert placeholder.substitute(Placeholder("hello"), {"hello": 5}) == 5

    with pytest.raises(placeholder.UndefinedSubstitution):
        placeholder.substitute(Placeholder("hello"), {})

    assert (
        placeholder.substitute(
            {"info": [1, Placeholder("hello"), 2, Placeholder("world")]},
            {"hello": 5, "world": 10},
        )
        == {"info": [1, 5, 2, 10]}
    )
