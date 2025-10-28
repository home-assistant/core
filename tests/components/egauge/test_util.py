"""Tests for eGauge utilities."""

import pytest

from homeassistant.components.egauge.util import _build_client_url


@pytest.mark.parametrize(
    ("host", "use_ssl", "expected"),
    [
        ("egauge.local", True, "https://egauge.local"),
        ("egauge.local", False, "http://egauge.local"),
        ("192.168.1.1", True, "https://192.168.1.1"),
        ("192.168.1.1", False, "http://192.168.1.1"),
    ],
)
def test_build_client_url(host: str, use_ssl: bool, expected: str) -> None:
    """Test building a URL for the eGauge client."""
    assert _build_client_url(host, use_ssl) == expected
