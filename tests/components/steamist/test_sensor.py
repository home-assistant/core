"""Tests for the steamist sensos."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import (
    MOCK_ASYNC_GET_STATUS_ACTIVE,
    MOCK_ASYNC_GET_STATUS_INACTIVE,
    _async_setup_entry_with_status,
)


async def test_steam_active(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values when steam is active."""
    await _async_setup_entry_with_status(hass, MOCK_ASYNC_GET_STATUS_ACTIVE)
    assert hass.states.get("sensor.steam_temperature").state == "39"
    assert hass.states.get("sensor.steam_minutes_remain").state == "14"


async def test_steam_inactive(hass: HomeAssistant) -> None:
    """Test that the binary sensors are setup with the expected values when steam is not active."""
    await _async_setup_entry_with_status(hass, MOCK_ASYNC_GET_STATUS_INACTIVE)
    assert hass.states.get("sensor.steam_temperature").state == "21"
    assert hass.states.get("sensor.steam_minutes_remain").state == "0"
