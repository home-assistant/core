"""Test base64 encoding and decoding functions for Home Assistant templates."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from tests.helpers.template.helpers import render


@pytest.mark.parametrize(
    ("value_template", "expected"),
    [
        ('{{ "homeassistant" | base64_encode }}', "aG9tZWFzc2lzdGFudA=="),
        ("{{ int('0F010003', base=16) | pack('>I') | base64_encode }}", "DwEAAw=="),
        ("{{ 'AA01000200150020' | from_hex | base64_encode }}", "qgEAAgAVACA="),
    ],
)
def test_base64_encode(hass: HomeAssistant, value_template: str, expected: str) -> None:
    """Test the base64_encode filter."""
    assert render(hass, value_template) == expected


def test_base64_decode(hass: HomeAssistant) -> None:
    """Test the base64_decode filter."""
    assert (
        render(hass, '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode }}') == "homeassistant"
    )
    assert (
        render(hass, '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode(None) }}')
        == b"homeassistant"
    )
    assert (
        render(hass, '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode("ascii") }}')
        == "homeassistant"
    )
