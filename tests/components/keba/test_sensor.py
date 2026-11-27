"""Tests for the KEBA charging station sensors."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import async_advance

pytestmark = pytest.mark.usefixtures("setup_keba")


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities, their unique IDs and states."""
    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 5
    for state in states:
        assert entity_registry.async_get(state.entity_id) == snapshot(
            name=f"{state.entity_id}-entry"
        )
        assert state == snapshot(name=f"{state.entity_id}-state")


@pytest.mark.parametrize("keba_fixture", ["p30_plugged.json", "p30_charging.json"])
async def test_sensor_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the sensor states with a car plugged in, and with a car charging."""
    states = sorted(
        hass.states.async_all(SENSOR_DOMAIN), key=lambda state: state.entity_id
    )
    assert len(states) == 5
    assert states == snapshot


async def test_sensors_follow_the_station(
    hass: HomeAssistant,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll carries new values from the library into the sensors."""
    keba_data.update(
        {
            "Curr user": 10.0,
            "Setenergy": 20.0,
            "P": 3.6,
            "E pres": 1.25,  # codespell:ignore pres
            "E total": 4856.9,
        }
    )

    await async_advance(hass, freezer, 5)

    assert hass.states.get("sensor.keba_p30_max_current").state == "10.0"
    assert hass.states.get("sensor.keba_p30_energy_target").state == "20.0"
    assert hass.states.get("sensor.keba_p30_charging_power").state == "3.6"
    assert hass.states.get("sensor.keba_p30_session_energy").state == "1.25"
    assert hass.states.get("sensor.keba_p30_total_energy").state == "4856.9"


async def test_charging_power_attributes(
    hass: HomeAssistant,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charging power sensor's per-phase attributes."""
    keba_data.update(
        {
            "PF": 99.7,
            "U1": 225,
            "U2": 227,
            "U3": 223,
            "I1": 15.8,
            "I2": 15.9,
            "I3": 15.7,
        }
    )

    await async_advance(hass, freezer, 5)

    attributes = hass.states.get("sensor.keba_p30_charging_power").attributes
    assert attributes["power_factor"] == 99.7
    assert attributes["voltage_u1"] == "225"
    assert attributes["voltage_u2"] == "227"
    assert attributes["voltage_u3"] == "223"
    assert attributes["current_i1"] == "15.8"
    assert attributes["current_i2"] == "15.9"
    assert attributes["current_i3"] == "15.7"


async def test_max_current_hardware_attribute(
    hass: HomeAssistant,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the max current sensor reports the library's hardware limit as is."""
    keba_data["Curr HW"] = 32000

    await async_advance(hass, freezer, 5)

    state = hass.states.get("sensor.keba_p30_max_current")
    assert state.attributes["max_current_hardware"] == 32000
