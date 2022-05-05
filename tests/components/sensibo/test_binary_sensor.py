"""The test for the sensibo binary sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.coordinator import SensiboDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .response import DATA_FROM_API

from tests.common import async_fire_time_changed


async def test_binary_sensor(hass: HomeAssistant, load_int: ConfigEntry) -> None:
    """Test the Sensibo binary sensor."""

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_alive")
    state2 = hass.states.get("binary_sensor.hallway_motion_sensor_main_sensor")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    state4 = hass.states.get("binary_sensor.hallway_room_occupied")
    assert state1.state == "on"
    assert state2.state == "on"
    assert state3.state == "on"
    assert state4.state == "on"

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][load_int.entry_id]
    coordinator.data.parsed["ABC999111"].motion_sensors["AABBCC"].alive = False
    coordinator.data.parsed["ABC999111"].motion_sensors["AABBCC"].motion = False

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_alive")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    assert state1.state == "off"
    assert state3.state == "off"
