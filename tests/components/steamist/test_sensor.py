"""Tests for the steamist sensos."""
from __future__ import annotations

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant

from . import (
    MOCK_ASYNC_GET_STATUS_ACTIVE,
    MOCK_ASYNC_GET_STATUS_INACTIVE,
    _async_setup_entry_with_status,
)


async def test_steam_active(hass: HomeAssistant) -> None:
    """Test that the sensors are setup with the expected values when steam is active."""
    await _async_setup_entry_with_status(hass, MOCK_ASYNC_GET_STATUS_ACTIVE)
    state = hass.states.get("sensor.steam_temperature")
    assert state.state == "39"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    state = hass.states.get("sensor.steam_minutes_remain")
    assert state.state == "14"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.MINUTES


async def test_steam_inactive(hass: HomeAssistant) -> None:
    """Test that the sensors are setup with the expected values when steam is not active."""
    await _async_setup_entry_with_status(hass, MOCK_ASYNC_GET_STATUS_INACTIVE)
    state = hass.states.get("sensor.steam_temperature")
    assert state.state == "21"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    state = hass.states.get("sensor.steam_minutes_remain")
    assert state.state == "0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.MINUTES
