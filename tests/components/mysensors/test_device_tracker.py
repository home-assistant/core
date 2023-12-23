"""Provide tests for mysensors device tracker platform."""
from __future__ import annotations

from collections.abc import Callable

from mysensors.sensor import Sensor

from homeassistant.components.device_tracker import ATTR_SOURCE_TYPE, SourceType
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant


async def test_gps_sensor(
    hass: HomeAssistant,
    gps_sensor: Sensor,
    receive_message: Callable[[str], None],
) -> None:
    """Test a gps sensor."""
    entity_id = "device_tracker.gps_sensor_1_1"
    altitude = 0
    latitude = "40.742"
    longitude = "-73.989"
    message_string = f"1;1;1;0;49;{latitude},{longitude},{altitude}\n"

    receive_message(message_string)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_SOURCE_TYPE] == SourceType.GPS
    assert state.attributes[ATTR_LATITUDE] == float(latitude)
    assert state.attributes[ATTR_LONGITUDE] == float(longitude)
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    latitude = "40.782"
    longitude = "-73.965"
    message_string = f"1;1;1;0;49;{latitude},{longitude},{altitude}\n"

    receive_message(message_string)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == STATE_NOT_HOME
    assert state.attributes[ATTR_SOURCE_TYPE] == SourceType.GPS
    assert state.attributes[ATTR_LATITUDE] == float(latitude)
    assert state.attributes[ATTR_LONGITUDE] == float(longitude)
