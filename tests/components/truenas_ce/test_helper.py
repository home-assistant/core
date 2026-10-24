"""Unit tests for ``homeassistant.components.truenas_ce.helper``.

Pure-function tests -- ``sanitize_host``/``scaled_data_unit`` have no Home
Assistant dependency, so no ``hass`` fixture is needed.
"""

from __future__ import annotations

import pytest

from homeassistant.components.truenas_ce.helper import sanitize_host


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("truenas.local", "truenas.local"),
        ("TrueNAS.Local", "truenas.local"),
        ("192.168.1.5", "192.168.1.5"),
        ("truenas.local:8443", "truenas.local:8443"),
        ("https://truenas.local/ui?tab=1", "truenas.local"),
        ("2001:db8::1", "[2001:db8::1]"),
        ("2001:DB8::1", "[2001:db8::1]"),
        ("::1", "[::1]"),
        ("[2001:db8::1]", "[2001:db8::1]"),
        ("[2001:db8::1]:8443", "[2001:db8::1]:8443"),
    ],
)
def test_sanitize_host(host: str, expected: str) -> None:
    """A bare IPv6 literal is bracketed; everything else is left as-is (lowercased)."""
    assert sanitize_host(host) == expected
