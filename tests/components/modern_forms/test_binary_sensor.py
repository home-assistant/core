"""Tests for the Modern Forms sensor platform."""
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.modern_forms import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_binary_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Modern Forms sensors."""

    await init_integration(hass, aioclient_mock)
    er.async_get(hass)

    # Light timer remaining time
    state = hass.states.get("binary_sensor.modernformsfan_light_sleep_timer_active")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:av-timer"
    assert state.state == "off"

    # Fan timer remaining time
    state = hass.states.get("binary_sensor.modernformsfan_fan_sleep_timer_active")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:av-timer"
    assert state.state == "off"
