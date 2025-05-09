"""Test Snoo Binary Sensors."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import async_init_integration, find_update_callback
from .const import MOCK_SNOO_DATA


async def test_binary_sensors(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test binary sensors and check test values are correctly set."""
    await async_init_integration(hass)
    assert len(hass.states.async_all("binary_sensor")) == 2
    assert (
        hass.states.get("binary_sensor.test_snoo_left_safety_clip").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("binary_sensor.test_snoo_right_safety_clip").state
        == STATE_UNAVAILABLE
    )
    find_update_callback(bypass_api, "random_num")(MOCK_SNOO_DATA)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("binary_sensor")) == 2
    assert hass.states.get("binary_sensor.test_snoo_left_safety_clip").state == STATE_ON
    assert (
        hass.states.get("binary_sensor.test_snoo_right_safety_clip").state == STATE_ON
    )
