"""Tests for Wibeee sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant

from .conftest import MOCK_HOST, MOCK_MAC


async def test_sensors_created(hass: HomeAssistant, loaded_entry) -> None:
    """Test that sensor entities are created."""
    states = hass.states.async_all("sensor")
    # Should have sensors for the discovered phases
    assert len(states) > 0


async def test_sensor_state_class(hass: HomeAssistant, loaded_entry) -> None:
    """Test sensor has correct state class."""
    states = hass.states.async_all("sensor")
    for state in states:
        if state.attributes.get("state_class") == SensorStateClass.MEASUREMENT:
            # Measurement sensors should have a device class or unit
            assert state.attributes.get("device_class") or state.attributes.get(
                "unit_of_measurement"
            )