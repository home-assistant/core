"""The sensor tests for the griddy platform."""

from unittest.mock import patch

from pydexcom import SessionError

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import GLUCOSE_READING, init_integration


async def test_sensors(hass: HomeAssistant) -> None:
    """Test we get sensor data."""
    await init_integration(hass)

    test_username_glucose_value = hass.states.get("sensor.test_username_glucose_value")
    assert test_username_glucose_value.state == str(GLUCOSE_READING.value)
    test_username_glucose_trend = hass.states.get("sensor.test_username_glucose_trend")
    assert test_username_glucose_trend.state == GLUCOSE_READING.trend_description


async def test_sensors_unknown(hass: HomeAssistant) -> None:
    """Test we handle sensor state unknown."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        return_value=None,
    ):
        await async_update_entity(hass, "sensor.test_username_glucose_value")
        await async_update_entity(hass, "sensor.test_username_glucose_trend")

    test_username_glucose_value = hass.states.get("sensor.test_username_glucose_value")
    assert test_username_glucose_value.state == STATE_UNKNOWN
    test_username_glucose_trend = hass.states.get("sensor.test_username_glucose_trend")
    assert test_username_glucose_trend.state == STATE_UNKNOWN


async def test_sensors_update_failed(hass: HomeAssistant) -> None:
    """Test we handle sensor update failed."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.dexcom.Dexcom.get_current_glucose_reading",
        side_effect=SessionError,
    ):
        await async_update_entity(hass, "sensor.test_username_glucose_value")
        await async_update_entity(hass, "sensor.test_username_glucose_trend")

    test_username_glucose_value = hass.states.get("sensor.test_username_glucose_value")
    assert test_username_glucose_value.state == STATE_UNAVAILABLE
    test_username_glucose_trend = hass.states.get("sensor.test_username_glucose_trend")
    assert test_username_glucose_trend.state == STATE_UNAVAILABLE
