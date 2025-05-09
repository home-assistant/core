"""Test Snoo Sensors."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import async_init_integration, find_update_callback
from .const import MOCK_SNOO_DATA


async def test_sensors(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test sensors and check test values are correctly set."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 2
    assert hass.states.get("sensor.test_snoo_state").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_snoo_time_left").state == STATE_UNAVAILABLE
    find_update_callback(bypass_api, "random_num")(MOCK_SNOO_DATA)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 2
    assert hass.states.get("sensor.test_snoo_state").state == "stop"
    assert hass.states.get("sensor.test_snoo_time_left").state == STATE_UNKNOWN
