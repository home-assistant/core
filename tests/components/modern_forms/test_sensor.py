"""Tests for the Modern Forms sensor platform."""
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT, TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.modern_forms import init_integration, modern_forms_timers_set_mock
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Modern Forms sensors."""

    # await init_integration(hass, aioclient_mock)
    await init_integration(hass, aioclient_mock)
    er.async_get(hass)

    # Light timer remaining time
    state = hass.states.get("sensor.modernformsfan_light_timer_remaining_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS
    assert state.state == "0"

    # Fan timer remaining time
    state = hass.states.get("sensor.modernformsfan_fan_timer_remaining_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS
    assert state.state == "0"


async def test_active_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Modern Forms sensors."""

    # await init_integration(hass, aioclient_mock)
    await init_integration(hass, aioclient_mock, mock_type=modern_forms_timers_set_mock)
    er.async_get(hass)

    # Light timer remaining time
    state = hass.states.get("sensor.modernformsfan_light_timer_remaining_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS
    assert int(state.state) > 0

    # Fan timer remaining time
    state = hass.states.get("sensor.modernformsfan_fan_timer_remaining_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:timer-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS
    assert int(state.state) > 0
