"""Tests for the KEBA charging station sensors."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import snapshot_keba_platform
from .conftest import POLL_INTERVAL, async_advance


async def test_sensors(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities, their unique IDs and states."""
    snapshot_keba_platform(hass, entity_registry, snapshot, Platform.SENSOR)


async def test_sensors_follow_the_station(
    hass: HomeAssistant,
    setup_keba: MagicMock,
    keba_data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll carries new values from the library into the sensors."""
    keba_data.update({"Curr user": 10.0, "Setenergy": 20.0, "P": 3.6})
    keba_data["E total"] = 12350.0

    await async_advance(hass, freezer, POLL_INTERVAL)

    assert hass.states.get("sensor.keba_p30_max_current").state == "10.0"
    assert hass.states.get("sensor.keba_p30_energy_target").state == "20.0"
    assert hass.states.get("sensor.keba_p30_charging_power").state == "3.6"
    assert hass.states.get("sensor.keba_p30_total_energy").state == "12350.0"
