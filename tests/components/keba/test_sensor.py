"""Tests for the KEBA charging station sensors."""

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import snapshot_keba_platform
from .conftest import POLL_INTERVAL, FakeKebaStation, async_advance


async def test_sensors(
    hass: HomeAssistant,
    setup_keba: FakeKebaStation,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities, their unique IDs and states."""
    snapshot_keba_platform(hass, entity_registry, snapshot, Platform.SENSOR)


async def test_sensors_follow_the_station(
    hass: HomeAssistant, setup_keba: FakeKebaStation, freezer: FrozenDateTimeFactory
) -> None:
    """Test a poll carries new report values into the sensors."""
    station = setup_keba
    station.push("2", **{"Curr user": 10000, "Setenergy": 200000})
    station.push("3", P=3600000, **{"E total": 123500000})

    await async_advance(hass, freezer, POLL_INTERVAL)

    assert hass.states.get("sensor.keba_p30_max_current").state == "10.0"
    assert hass.states.get("sensor.keba_p30_energy_target").state == "20.0"
    assert hass.states.get("sensor.keba_p30_charging_power").state == "3.6"
    assert hass.states.get("sensor.keba_p30_total_energy").state == "12350.0"


async def test_report_2_alone_currently_does_not_update(
    hass: HomeAssistant, setup_keba: FakeKebaStation, freezer: FrozenDateTimeFactory
) -> None:
    """Test changes in report 2 only show up once report 3 or 100 arrives.

    The library returns early after reports 1 and 2 without notifying the
    integration, so a station that stops answering report 3 and 100 leaves
    the entities stale.
    """
    station = setup_keba
    reports_3_and_100 = {key: station.reports.pop(key) for key in ("3", "100")}
    station.push("2", **{"Curr user": 10000})

    await async_advance(hass, freezer, POLL_INTERVAL)
    assert hass.states.get("sensor.keba_p30_max_current").state == "16.0"

    station.reports.update(reports_3_and_100)
    await async_advance(hass, freezer, POLL_INTERVAL)
    assert hass.states.get("sensor.keba_p30_max_current").state == "10.0"


async def test_session_energy_currently_from_report_100(
    hass: HomeAssistant, setup_keba: FakeKebaStation, freezer: FrozenDateTimeFactory
) -> None:
    """Test report 100 overwrites report 3's present-session energy.

    Both reports carry the same present-session energy key; the library
    merges them into one dict and report 100 is requested last.
    """
    station = setup_keba
    station.push("3", **{"E pres": 10000})  # codespell:ignore pres
    station.push("100", **{"E pres": 20000})  # codespell:ignore pres

    await async_advance(hass, freezer, POLL_INTERVAL)

    assert hass.states.get("sensor.keba_p30_session_energy").state == "2.0"


async def test_hardware_current_currently_unscaled(
    hass: HomeAssistant, setup_keba: FakeKebaStation
) -> None:
    """Test the max_current_hardware attribute is in mA, not A.

    Report 2's "Curr HW" is scaled to amperes, but report 100 also carries
    "Curr HW" and the library stores it unscaled, after report 2.
    """
    state = hass.states.get("sensor.keba_p30_max_current")
    assert state.attributes["max_current_hardware"] == 16000
