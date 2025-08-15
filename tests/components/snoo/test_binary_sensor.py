"""Test Snoo Binary Sensors."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import async_init_integration, find_update_callback
from .const import MOCK_SNOO_DATA


async def test_binary_sensors(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test binary sensors and check test values are correctly set."""
    await async_init_integration(hass)
    # 2 device sensors + 4 baby sensors = 6 total
    assert len(hass.states.async_all("binary_sensor")) == 6
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
    assert len(hass.states.async_all("binary_sensor")) == 6
    assert hass.states.get("binary_sensor.test_snoo_left_safety_clip").state == STATE_ON
    assert (
        hass.states.get("binary_sensor.test_snoo_right_safety_clip").state == STATE_ON
    )

    baby_binary_sensors = [
        "binary_sensor.test_baby_disabled_limiter",
        "binary_sensor.test_baby_car_ride_mode",
        "binary_sensor.test_baby_motion_limiter",
        "binary_sensor.test_baby_weaning",
    ]

    for sensor_id in baby_binary_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Baby sensor {sensor_id} should exist"
        assert state.state != STATE_UNAVAILABLE
