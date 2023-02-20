"""Test the Envisalink binary sensors."""

import datetime

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.envisalink.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_LAST_TRIP_TIME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util


async def test_binary_sensor_state(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test the createion and values of the Envisalink binary sensors."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    state = hass.states.get("binary_sensor.test_alarm_name_zone_1")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("zone") == 1
    assert state.attributes.get("last_fault") is None  # TODO
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OPENING


async def test_binary_sensor_update(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test updating a zone's state."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    zone_info = {
        1: 100,
        3: 5000,
        7: 70000 * 5,  # Make sure we exceed the max zone timer value
    }
    for zone, seconds_ago in zone_info.items():
        controller.controller.alarm_state["zone"][zone]["status"]["open"] = True
        controller.controller.alarm_state["zone"][zone]["last_fault"] = seconds_ago
    controller.async_zones_updated_callback(zone_info.keys())
    await hass.async_block_till_done()

    for zone, seconds_ago in zone_info.items():
        state = hass.states.get(f"binary_sensor.test_alarm_name_zone_{zone}")
        assert state
        assert state.state == STATE_ON

        last_trip_time = state.attributes.get(ATTR_LAST_TRIP_TIME)

        if seconds_ago < (65536 * 5):
            now = dt_util.now()
            fault_time = datetime.datetime.fromisoformat(last_trip_time)
            delta = now - fault_time
            assert abs(delta) < datetime.timedelta(seconds=seconds_ago + 5)
        else:
            assert not last_trip_time
