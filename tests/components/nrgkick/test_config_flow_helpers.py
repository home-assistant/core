"""Unit-style tests for NRGkick config flow helpers and defensive paths."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.components.nrgkick.config_flow import _normalize_host


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://example.com:1234/path", "example.com:1234"),
        ("https://example.com/path", "example.com:443"),
        ("example.com/some/path", "example.com"),
        ("192.168.1.10/", "192.168.1.10"),
    ],
)
def test_normalize_host(value: str, expected: str) -> None:
    """Test host normalization."""
    assert _normalize_host(value) == expected


@pytest.mark.parametrize("value", ["", "   "])
def test_normalize_host_empty(value: str) -> None:
    """Test host normalization with empty input."""
    with pytest.raises(vol.Invalid):
        _normalize_host(value)
