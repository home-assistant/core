"""Test base64 encoding and decoding functions for Home Assistant templates."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template


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
    assert template.Template(value_template, hass).async_render() == expected


def test_base64_decode(hass: HomeAssistant) -> None:
    """Test the base64_decode filter."""
    assert (
        template.Template(
            '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode }}', hass
        ).async_render()
        == "homeassistant"
    )
    assert (
        template.Template(
            '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode(None) }}', hass
        ).async_render()
        == b"homeassistant"
    )
    assert (
        template.Template(
            '{{ "aG9tZWFzc2lzdGFudA==" | base64_decode("ascii") }}', hass
        ).async_render()
        == "homeassistant"
    )
