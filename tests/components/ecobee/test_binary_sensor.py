"""Tests for ecobee binary sensors."""

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .common import setup_platform

pytestmark = pytest.mark.usefixtures("mock_ecobee")


async def test_occupancy_sensor(hass: HomeAssistant) -> None:
    """Test the occupancy binary sensor."""
    await setup_platform(hass, Platform.BINARY_SENSOR)

    state = hass.states.get("binary_sensor.remote_sensor_1_occupancy")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["device_class"] == BinarySensorDeviceClass.OCCUPANCY


async def test_alert_sensor_firing(hass: HomeAssistant) -> None:
    """Test alert binary sensor when an alert is actively firing."""
    await setup_platform(hass, Platform.BINARY_SENSOR)

    state = hass.states.get("binary_sensor.ecobee_furnace_filter")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM
    assert state.attributes["alert_number"] == 3130
    assert state.attributes["equipment_type"] == "furnaceFilter"
    assert state.attributes["text"] == "Change Furnace Filter"
    assert state.attributes["severity"] == "low"


async def test_alert_sensor_not_firing(hass: HomeAssistant) -> None:
    """Test alert binary sensor when no matching alert is firing."""
    await setup_platform(hass, Platform.BINARY_SENSOR)

    state = hass.states.get("binary_sensor.ecobee_uv_lamp")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM
    assert state.attributes["alert_number"] == 3135
    assert state.attributes["equipment_type"] == "uvLamp"


async def test_disabled_equipment_not_created(hass: HomeAssistant) -> None:
    """Test that disabled equipment reminders don't create entities."""
    await setup_platform(hass, Platform.BINARY_SENSOR)

    state = hass.states.get("binary_sensor.ecobee_humidifier_filter")
    assert state is None


async def test_no_alert_entities_when_no_equipment(hass: HomeAssistant) -> None:
    """Test that thermostats with no equipment notifications don't create alert entities."""
    await setup_platform(hass, Platform.BINARY_SENSOR)

    state = hass.states.get("binary_sensor.ecobee2_furnace_filter")
    assert state is None
