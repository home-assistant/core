"""Test the mvglive sensor platform."""

from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
from mvg import MvgApiError, TransportType
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mvglive.const import (
    CONF_DESTINATIONS,
    CONF_LINES,
    CONF_NUMBER,
    CONF_PRODUCTS,
    CONF_TIMEOFFSET,
    DOMAIN,
)
from homeassistant.components.mvglive.sensor import (
    MAX_DEPARTURES,
    PLATFORM_SCHEMA,
    async_setup_platform,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import TEST_DEPARTURES, TEST_STATION, TEST_STATIONS

TEST_ENTITY_ID = "sensor.hauptbahnhof"


def test_platform_schema_accepts_deprecated_directions() -> None:
    """Test PLATFORM_SCHEMA still accepts the deprecated `directions` key."""
    PLATFORM_SCHEMA(
        {
            "platform": "mvglive",
            "nextdeparture": [{"station": "Hauptbahnhof", "directions": "Feldmoching"}],
        }
    )


@pytest.mark.usefixtures("mvg_api")
async def test_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the departures sensor entity."""
    freezer.move_to("2026-08-19 12:00:00+00:00")
    await setup_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("filters", "limit", "expected_minutes"),
    [
        pytest.param({}, 2, [5, 6], id="no_local_filters"),
        pytest.param(
            {CONF_DESTINATIONS: ["Feldmoching"]},
            MAX_DEPARTURES,
            [6, 7],
            id="destination",
        ),
        pytest.param({CONF_LINES: ["U2"]}, MAX_DEPARTURES, [6, 8], id="line"),
        pytest.param(
            {CONF_DESTINATIONS: ["Feldmoching"], CONF_LINES: ["U2"]},
            MAX_DEPARTURES,
            [6, 9],
            id="destination_and_line",
        ),
    ],
)
async def test_sensor_options(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mvg_api: dict[str, AsyncMock],
    freezer: FrozenDateTimeFactory,
    filters: dict[str, list[str]],
    limit: int,
    expected_minutes: list[int],
) -> None:
    """Test API options and local filtering before limiting departures."""
    freezer.move_to("2026-08-19 12:00:00+00:00")
    now = int(dt_util.utcnow().timestamp())
    mvg_api["departures_async"].return_value = [
        {
            "destination": destination,
            "line": line,
            "time": now + minutes * 60,
            "icon": "mdi:subway",
        }
        for minutes, destination, line in (
            (4, "Feldmoching", "U2"),
            (5, "Messestadt Ost", "U8"),
            (6, "Feldmoching", "U2"),
            (7, "Feldmoching", "U8"),
            (8, "Messestadt Ost", "U2"),
            (9, "Feldmoching", "U2"),
            (10, "Feldmoching", "U2"),
        )
    ]
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **filters,
            CONF_PRODUCTS: ["U-Bahn"],
            CONF_TIMEOFFSET: 5,
            CONF_NUMBER: 2,
        },
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mvg_api["departures_async"].assert_awaited_once_with(
        station_id=TEST_STATION["id"],
        limit=limit,
        offset=5,
        transport_types=[TransportType.UBAHN],
        session=async_get_clientsession(hass),
    )
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == str(expected_minutes[0])
    assert [
        departure["time_in_mins"] for departure in state.attributes["departures"]
    ] == expected_minutes


@pytest.mark.parametrize(
    "icon",
    [pytest.param(None, id="null"), pytest.param("", id="empty")],
)
async def test_sensor_missing_icon(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mvg_api: dict[str, AsyncMock],
    icon: str | None,
) -> None:
    """Test fallback icons for empty API icons."""
    mvg_api["departures_async"].return_value = [
        {"destination": "Feldmoching", "line": "U2", "time": 32503683600, "icon": icon}
    ]
    await setup_integration(hass, config_entry)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.attributes["icon"] == "mdi:clock"


@pytest.mark.parametrize(
    ("initial_error", "initial_state"),
    [
        pytest.param(None, "5", id="initial_success"),
        pytest.param(MvgApiError("offline"), STATE_UNAVAILABLE, id="initial_failure"),
    ],
)
async def test_sensor_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mvg_api: dict[str, AsyncMock],
    freezer: FrozenDateTimeFactory,
    initial_error: MvgApiError | None,
    initial_state: str,
) -> None:
    """Test availability on API failure, recovery, and empty results."""
    freezer.move_to("2026-08-19 12:00:00+00:00")
    departures = [
        {**TEST_DEPARTURES[0], "time": int(dt_util.utcnow().timestamp()) + 300}
    ]
    api = mvg_api["departures_async"]
    api.return_value = departures
    api.side_effect = initial_error
    await setup_integration(hass, config_entry)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == initial_state

    api.side_effect = MvgApiError("offline")
    await async_update_entity(hass, TEST_ENTITY_ID)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "departures" not in state.attributes

    api.side_effect = None
    await async_update_entity(hass, TEST_ENTITY_ID)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == "5"
    assert len(state.attributes["departures"]) == 1

    api.return_value = []
    await async_update_entity(hass, TEST_ENTITY_ID)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("station_config", "entity_id", "expected_name"),
    [
        pytest.param(
            {"station": "Hauptbahnhof"},
            "sensor.hauptbahnhof",
            "Hauptbahnhof",
            id="canonical_name",
        ),
        pytest.param({"station": "Hbf"}, "sensor.hbf", "Hbf", id="station_alias"),
        pytest.param(
            {"station": "Hbf", "name": "My station"},
            "sensor.my_station",
            "My station",
            id="custom_name",
        ),
    ],
)
@pytest.mark.usefixtures("mvg_api")
async def test_yaml_import(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    station_config: dict[str, str],
    entity_id: str,
    expected_name: str,
) -> None:
    """Test YAML import creates a sensor and an idempotent repair."""
    config = PLATFORM_SCHEMA({"platform": DOMAIN, "nextdeparture": [station_config]})
    assert await async_setup_component(hass, "sensor", {"sensor": [config]})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["friendly_name"] == expected_name
    assert entries[0].title == expected_name
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == entries[0].entry_id
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.5.0"

    add_entities = Mock()
    await async_setup_platform(hass, config, add_entities)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == entries
    add_entities.assert_not_called()


@pytest.mark.parametrize(
    ("stations", "responses", "entry_count", "recovery_responses"),
    [
        pytest.param(
            [{"station": "Missing"}],
            [None],
            0,
            [TEST_STATIONS[1]],
            id="all_failed",
        ),
        pytest.param(
            [{"station": "Hauptbahnhof"}, {"station": "Missing"}],
            [TEST_STATION, None],
            1,
            [TEST_STATION, TEST_STATIONS[1]],
            id="mixed",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_yaml_invalid_station(
    hass: HomeAssistant,
    mvg_api: dict[str, AsyncMock],
    issue_registry: ir.IssueRegistry,
    stations: list[dict[str, str]],
    responses: list[dict[str, str] | None],
    entry_count: int,
    recovery_responses: list[dict[str, str]],
) -> None:
    """Test recovery from invalid YAML stations and removal of repairs."""
    mvg_api["station_async"].side_effect = responses
    config = PLATFORM_SCHEMA({"platform": DOMAIN, "nextdeparture": stations})
    await async_setup_platform(hass, config, Mock())
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == entry_count
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_station_Missing"
    )
    assert issue is not None
    assert issue.translation_placeholders == {"station": "Missing"}
    assert issue.breaks_in_ha_version == "2027.5.0"

    imported_entries = hass.config_entries.async_entries(DOMAIN)
    mvg_api["station_async"].side_effect = recovery_responses
    await async_setup_platform(hass, config, Mock())
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == len(stations)
    assert all(entry in entries for entry in imported_entries)
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_invalid_station_Missing"
        )
        is None
    )


@pytest.mark.parametrize(
    "responses",
    [
        pytest.param([TEST_STATION, MvgApiError("offline")], id="second_fails"),
        pytest.param([MvgApiError("offline"), TEST_STATION], id="first_fails"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_yaml_import_retry(
    hass: HomeAssistant,
    mvg_api: dict[str, AsyncMock],
    issue_registry: ir.IssueRegistry,
    responses: list[dict[str, str] | MvgApiError],
) -> None:
    """Test transient imports retry without duplicating successful entries."""
    config = PLATFORM_SCHEMA(
        {
            "platform": DOMAIN,
            "nextdeparture": [
                {"station": "Hauptbahnhof", "name": "First"},
                {"station": "Hauptbahnhof", "name": "Second"},
            ],
        }
    )
    mvg_api["station_async"].side_effect = responses
    with pytest.raises(PlatformNotReady):
        await async_setup_platform(hass, config, Mock())
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is None
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_Hauptbahnhof"
    )

    imported_entries = hass.config_entries.async_entries(DOMAIN)
    mvg_api["station_async"].side_effect = None
    await async_setup_platform(hass, config, Mock())
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert all(entry in entries for entry in imported_entries)
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_yaml_import_issue_cannot_connect_Hauptbahnhof"
        )
        is None
    )
