"""The test for the sensibo select platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.model import SensiboData
from pytest import MonkeyPatch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo sensor."""

    state1 = hass.states.get("sensor.hallway_motion_sensor_battery_voltage")
    state2 = hass.states.get("sensor.kitchen_pm2_5")
    state3 = hass.states.get("sensor.kitchen_pure_sensitivity")
    assert state1.state == "3000"
    assert state2.state == "1"
    assert state3.state == "n"
    assert state2.attributes == {
        "state_class": "measurement",
        "unit_of_measurement": "µg/m³",
        "device_class": "pm25",
        "icon": "mdi:air-filter",
        "friendly_name": "Kitchen PM2.5",
    }

    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pm25", 2)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("sensor.kitchen_pm2_5")
    assert state1.state == "2"
