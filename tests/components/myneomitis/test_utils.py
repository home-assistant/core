"""Tests for utility functions in the MyNeomitis integration."""

from homeassistant.components.myneomitis.utils import (
    PRESET_MODE_MAP,
    PRESET_MODE_MAP_RELAIS,
    PRESET_MODE_MAP_UFH,
    REVERSE_PRESET_MODE_MAP,
    REVERSE_PRESET_MODE_MAP_RELAIS,
    REVERSE_PRESET_MODE_MAP_UFH,
)


def test_preset_mode_maps() -> None:
    """Test that preset mode maps are correctly defined."""
    assert PRESET_MODE_MAP["comfort"] == 1
    assert PRESET_MODE_MAP["eco"] == 2
    assert PRESET_MODE_MAP["antifrost"] == 3
    assert PRESET_MODE_MAP_RELAIS["on"] == 1
    assert PRESET_MODE_MAP_RELAIS["off"] == 2
    assert PRESET_MODE_MAP_UFH["heating"] == 0
    assert PRESET_MODE_MAP_UFH["cooling"] == 1


def test_reverse_preset_mode_maps() -> None:
    """Test that reverse preset mode maps are correctly defined."""
    assert REVERSE_PRESET_MODE_MAP[1] == "comfort"
    assert REVERSE_PRESET_MODE_MAP[2] == "eco"
    assert REVERSE_PRESET_MODE_MAP_RELAIS[1] == "on"
    assert REVERSE_PRESET_MODE_MAP_RELAIS[2] == "off"
    assert REVERSE_PRESET_MODE_MAP_UFH[0] == "heating"
    assert REVERSE_PRESET_MODE_MAP_UFH[1] == "cooling"
