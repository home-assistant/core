"""Tests for the BACnet binary sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_binary_sensors_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that binary sensors are created for binary BACnet objects."""
    await init_integration(hass)

    # Occupancy Sensor (binary-input,0) - value 1 = on
    state = hass.states.get("binary_sensor.test_hvac_controller_occupancy_sensor")
    assert state is not None
    assert state.state == STATE_ON

    # Filter Status (binary-input,1) - value 0 = off
    state = hass.states.get("binary_sensor.test_hvac_controller_filter_status")
    assert state is not None
    assert state.state == STATE_OFF

    # Fan Command (binary-output,0) - value 1 = on
    state = hass.states.get("binary_sensor.test_hvac_controller_fan_command")
    assert state is not None
    assert state.state == STATE_ON

    # Alarm Active (binary-value,0) - value 0 = off
    state = hass.states.get("binary_sensor.test_hvac_controller_alarm_active")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensor_count(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test the correct number of binary sensors are created."""
    await init_integration(hass)

    binary_sensor_states = hass.states.async_entity_ids("binary_sensor")
    # We expect 4 binary sensors:
    # binary-input,0 (Occupancy), binary-input,1 (Filter),
    # binary-output,0 (Fan), binary-value,0 (Alarm)
    assert len(binary_sensor_states) == 4
