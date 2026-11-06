"""Tests for the GBFS sensors."""

from dataclasses import replace

from aiohttp import ClientError
from aiomobilitydatabase.feeds import VehicleType
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gbfs.const import (
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
    UPDATE_INTERVAL,
)
from homeassistant.components.gbfs.sensor import vehicle_group
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_URL, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import V2_URL, V3_URL, mock_feed

MAIN_ST = "sensor.main_st_1st_ave"


def _station(station_id: str, title: str) -> ConfigSubentryDataWithId:
    return ConfigSubentryDataWithId(
        data={CONF_STATION_ID: station_id},
        subentry_id=f"station_{station_id}",
        subentry_type=SUBENTRY_TYPE_STATION,
        title=title,
        unique_id=station_id,
    )


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors of a docked station with classic bikes and e-bikes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_v3_feed")
async def test_virtual_station_has_no_docks(hass: HomeAssistant) -> None:
    """Test a virtual station gets no docks sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example_bikes",
        data={CONF_URL: V3_URL},
        subentries_data=[_station("s2", "Park Ave & 2nd St")],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.park_ave_2nd_st_vehicles_available").state == "1"
    assert hass.states.get("sensor.park_ave_2nd_st_e_bikes").state == "1"
    assert hass.states.get("sensor.park_ave_2nd_st_classic_bikes").state == "0"
    assert hass.states.get("sensor.park_ave_2nd_st_docks_available") is None


@pytest.mark.usefixtures("mock_v3_feed")
async def test_uninstalled_station_is_unavailable(hass: HomeAssistant) -> None:
    """Test a station reporting is_installed false is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example_bikes",
        data={CONF_URL: V3_URL},
        subentries_data=[_station("s3", "River Rd")],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.river_rd_vehicles_available").state == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("mock_v3_feed")
async def test_station_removed_from_feed_is_unavailable(hass: HomeAssistant) -> None:
    """Test a station no longer in the feed is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="example_bikes",
        data={CONF_URL: V3_URL},
        subentries_data=[_station("gone", "Gone St")],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.gone_st_vehicles_available").state == STATE_UNAVAILABLE
    )
    assert hass.states.get("sensor.gone_st_docks_available") is None


async def test_system_without_vehicle_types(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a v2.3 system without vehicle types gets only totals."""
    mock_feed(aioclient_mock, "v2")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="old_bikes",
        data={CONF_URL: V2_URL},
        subentries_data=[_station("a", "Gare")],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.gare_vehicles_available").state == "4"
    assert hass.states.get("sensor.gare_docks_available").state == "6"
    assert hass.states.async_entity_ids("sensor") == [
        "sensor.gare_vehicles_available",
        "sensor.gare_docks_available",
    ]


async def test_group_sensor_unknown_without_per_type_counts(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a station that stops reporting per-type counts has unknown group sensors."""
    coordinator = init_integration.runtime_data
    station = replace(coordinator.data["s1"], vehicle_types_available=None)
    coordinator.async_set_updated_data({"s1": station})

    assert hass.states.get(f"{MAIN_ST}_classic_bikes").state == STATE_UNKNOWN
    assert hass.states.get(f"{MAIN_ST}_vehicles_available").state == "5"


@pytest.mark.usefixtures("init_integration")
async def test_poll_failure_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors go unavailable when polling fails and recover after."""
    entity_id = f"{MAIN_ST}_vehicles_available"
    assert hass.states.get(entity_id).state == "5"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://gbfs.example.com/v3/station_status.json", exc=ClientError()
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    mock_feed(aioclient_mock, "v3")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "5"


@pytest.mark.parametrize(
    ("form_factor", "propulsion_type", "group"),
    [
        ("bicycle", "human", "classic_bikes"),
        ("bicycle", None, "classic_bikes"),
        ("bicycle", "electric_assist", "e_bikes"),
        ("bicycle", "electric", "e_bikes"),
        ("bicycle", "future_propulsion", "e_bikes"),
        ("cargo_bicycle", "electric_assist", "cargo_bikes"),
        ("scooter_standing", "electric", "scooters"),
        ("scooter_seated", "electric", "scooters"),
        ("scooter", "electric", "scooters"),
        ("moped", "electric", "mopeds"),
        ("car", "combustion", "cars"),
        ("other", "human", "other_vehicles"),
        ("hoverboard", "electric", None),
        (None, None, None),
    ],
)
def test_vehicle_group(
    form_factor: str | None, propulsion_type: str | None, group: str | None
) -> None:
    """Test every GBFS form factor maps to one sensor group."""
    vehicle_type = VehicleType(
        id="t",
        form_factor=form_factor,
        propulsion_type=propulsion_type,
        name=None,
        max_range_m=None,
        rider_capacity=None,
    )
    assert vehicle_group(vehicle_type) == group
