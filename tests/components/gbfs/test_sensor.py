"""Tests for the GBFS sensors."""

from datetime import timedelta
from typing import Any

from aiohttp import ClientError
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
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_URL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MIXED_URL, V2_URL, V3_URL, mock_feed, serve_edited_v3_feed

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


@pytest.mark.parametrize(
    ("version", "url", "system_id", "stations"),
    [
        pytest.param(
            "v3", V3_URL, "example_bikes", [("s2", "Park Ave & 2nd St")], id="virtual"
        ),
        pytest.param(
            "v3", V3_URL, "example_bikes", [("s3", "River Rd")], id="uninstalled"
        ),
        pytest.param(
            "v3", V3_URL, "example_bikes", [("gone", "Gone St")], id="removed_from_feed"
        ),
        pytest.param(
            "v2", V2_URL, "old_bikes", [("a", "Gare")], id="without_vehicle_types"
        ),
        pytest.param(
            "v3_mixed",
            MIXED_URL,
            "mixed_bikes",
            [("m1", "Mixed One"), ("m2", "Mixed Two")],
            id="every_form_factor",
        ),
    ],
)
async def test_station_variants(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    version: str,
    url: str,
    system_id: str,
    stations: list[tuple[str, str]],
) -> None:
    """Test the sensors of stations in the different feed shapes."""
    mock_feed(aioclient_mock, version)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Variant Bikes",
        unique_id=system_id,
        data={CONF_URL: url},
        subentries_data=[_station(*station) for station in stations],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


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


async def test_station_missing_from_status(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a station without a status row is unavailable."""

    def drop_s2(document: dict[str, Any]) -> None:
        document["data"]["stations"] = [
            station
            for station in document["data"]["stations"]
            if station["station_id"] != "s2"
        ]

    await serve_edited_v3_feed(hass, aioclient_mock, {"station_status": drop_s2})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Variant Bikes",
        unique_id="example_bikes",
        data={CONF_URL: V3_URL},
        subentries_data=[_station("s2", "Park Ave & 2nd St")],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_new_vehicle_type_counts_in_its_group(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a vehicle type added to the feed counts without a reload."""
    entity_id = f"{MAIN_ST}_e_bikes"
    assert hass.states.get(entity_id).state == "2"

    def add_type(document: dict[str, Any]) -> None:
        document["data"]["vehicle_types"].append(
            {
                "vehicle_type_id": "ebike_xl",
                "form_factor": "bicycle",
                "propulsion_type": "electric",
            }
        )

    def count_type(document: dict[str, Any]) -> None:
        document["data"]["stations"][0]["vehicle_types_available"].append(
            {"vehicle_type_id": "ebike_xl", "count": 4}
        )

    await serve_edited_v3_feed(
        hass,
        aioclient_mock,
        {"vehicle_types": add_type, "station_status": count_type},
    )
    freezer.tick(timedelta(seconds=300))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "6"


async def test_docks_sensor_for_station_without_status_at_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a docked station without a status row still gets a docks sensor."""

    def drop_s1(document: dict[str, Any]) -> None:
        document["data"]["stations"] = [
            station
            for station in document["data"]["stations"]
            if station["station_id"] != "s1"
        ]

    await serve_edited_v3_feed(hass, aioclient_mock, {"station_status": drop_s1})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Variant Bikes",
        unique_id="example_bikes",
        data={CONF_URL: V3_URL},
        subentries_data=[_station("s1", "Main St & 1st Ave")],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"{MAIN_ST}_docks_available"
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    mock_feed(aioclient_mock, "v3")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "5"


@pytest.mark.usefixtures("init_integration")
async def test_empty_vehicle_breakdown_counts_zero(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty per-type breakdown means no vehicles, not unknown."""

    def empty_station(document: dict[str, Any]) -> None:
        station = document["data"]["stations"][0]
        station["num_vehicles_available"] = 0
        station["vehicle_types_available"] = []

    await serve_edited_v3_feed(hass, aioclient_mock, {"station_status": empty_station})
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"{MAIN_ST}_classic_bikes").state == "0"
    assert hass.states.get(f"{MAIN_ST}_e_bikes").state == "0"
