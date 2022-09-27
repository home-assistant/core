"""The test for the sensibo binary sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pysensibo.model import SensiboData
from pytest import MonkeyPatch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    load_int: ConfigEntry,
    monkeypatch: MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo binary sensor."""

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_alive")
    state2 = hass.states.get("binary_sensor.hallway_motion_sensor_main_sensor")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    state4 = hass.states.get("binary_sensor.hallway_room_occupied")
    state5 = hass.states.get(
        "binary_sensor.kitchen_pure_boost_linked_with_indoor_air_quality"
    )
    state6 = hass.states.get(
        "binary_sensor.kitchen_pure_boost_linked_with_outdoor_air_quality"
    )
    assert state1.state == "on"
    assert state2.state == "on"
    assert state3.state == "on"
    assert state4.state == "on"
    assert state5.state == "on"
    assert state6.state == "off"

    monkeypatch.setattr(
        get_data.parsed["ABC999111"].motion_sensors["AABBCC"], "alive", False
    )
    monkeypatch.setattr(
        get_data.parsed["ABC999111"].motion_sensors["AABBCC"], "motion", False
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
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
