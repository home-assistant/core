"""The test for the sensibo select platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.model import PureAQI, SensiboData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Sensibo sensor."""

    state1 = hass.states.get("sensor.hallway_motion_sensor_battery_voltage")
    state2 = hass.states.get("sensor.kitchen_pure_aqi")
    state3 = hass.states.get("sensor.kitchen_pure_sensitivity")
    state4 = hass.states.get("sensor.hallway_climate_react_low_temperature_threshold")
    assert state1.state == "3000"
    assert state2.state == "good"
    assert state3.state == "n"
    assert state4.state == "0.0"
    assert state2.attributes == snapshot
    assert state4.attributes == snapshot

    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pm25_pure", PureAQI(2))

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("sensor.kitchen_pure_aqi")
    assert state1.state == "moderate"
