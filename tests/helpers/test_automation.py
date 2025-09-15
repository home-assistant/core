"""Test automation helpers."""

import pytest

from homeassistant.helpers.automation import (
    get_absolute_description_key,
    get_relative_description_key,
)


@pytest.mark.parametrize(
    ("relative_key", "absolute_key"),
    [
        ("turned_on", "homeassistant.turned_on"),
        ("_", "homeassistant"),
        ("_state", "state"),
    ],
)
def test_absolute_description_key(relative_key: str, absolute_key: str) -> None:
    """Test absolute description key."""
    DOMAIN = "homeassistant"
    assert get_absolute_description_key(DOMAIN, relative_key) == absolute_key


@pytest.mark.parametrize(
    ("relative_key", "absolute_key"),
    [
        ("turned_on", "homeassistant.turned_on"),
        ("_", "homeassistant"),
        ("_state", "state"),
    ],
)
def test_relative_description_key(relative_key: str, absolute_key: str) -> None:
    """Test relative description key."""
    DOMAIN = "homeassistant"
    assert get_relative_description_key(DOMAIN, absolute_key) == relative_key
