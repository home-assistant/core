"""Tests for Rain Bird utilities."""

from __future__ import annotations

import pytest

from homeassistant.components.rainbird.util import normalize_rainbird_host


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("example.com", "example.com"),
        ("example.com/", "example.com"),
        ("192.168.1.1", "192.168.1.1"),
        ("https://example.com", "example.com"),
        ("http://example.com", "example.com"),
        (" https://example.com ", "example.com"),
        ("https://example.com/", "example.com"),
        ("http://example.com/path/to/api", "example.com"),
        ("https://example.com/stick/", "example.com"),
        ("http://example.com:8080", "example.com:8080"),
        ("http://example.com:8080/", "example.com:8080"),
        ("https://example.com:8080/stick", "example.com:8080"),
        ("https://example.com:abc", "example.com"),
        ("https://example.com:abc/stick", "example.com"),
        ("//example.com", "example.com"),
        ("//example.com:8080/stick", "example.com:8080"),
    ],
)
def test_normalize_rainbird_host(host: str, expected: str) -> None:
    """Test host normalization utility."""
    assert normalize_rainbird_host(host) == expected
