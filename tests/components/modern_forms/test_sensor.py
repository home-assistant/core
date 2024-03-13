"""Tests for the Modern Forms sensor platform."""
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON
from homeassistant.core import HomeAssistant

from . import init_integration, modern_forms_timers_set_mock

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Modern Forms sensors."""

    # await init_integration(hass, aioclient_mock)
    await init_integration(hass, aioclient_mock)

    # Light timer remaining time
    state = hass.states.get("sensor.modernformsfan_light_sleep_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.state == "unknown"

    # Fan timer remaining time
    state = hass.states.get("sensor.modernformsfan_fan_sleep_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.state == "unknown"


async def test_active_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Modern Forms sensors."""

    # await init_integration(hass, aioclient_mock)
    await init_integration(hass, aioclient_mock, mock_type=modern_forms_timers_set_mock)

    # Light timer remaining time
    state = hass.states.get("sensor.modernformsfan_light_sleep_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    datetime.fromisoformat(state.state)

    # Fan timer remaining time
    state = hass.states.get("sensor.modernformsfan_fan_sleep_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    datetime.fromisoformat(state.state)
