"""Tests for the Modern Forms sensor platform."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from . import init_integration, init_integration_gen4, modern_forms_timers_set_mock

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
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert state.state == "unknown"

    # Fan timer remaining time
    state = hass.states.get("sensor.modernformsfan_fan_sleep_time")
    assert state
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
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    datetime.fromisoformat(state.state)

    # Fan timer remaining time
    state = hass.states.get("sensor.modernformsfan_fan_sleep_time")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    datetime.fromisoformat(state.state)


async def test_no_sleep_timer_sensors_on_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the sleep-timer sensors aren't created for Gen4 fans."""
    await init_integration_gen4(hass, aioclient_mock)

    assert hass.states.get("sensor.modernformsfan_fan_sleep_time") is None
    assert hass.states.get("sensor.modernformsfan_light_sleep_time") is None
