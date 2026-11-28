"""Tests for the GTFS calendar."""

from datetime import timedelta
import json
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.components.gtfs.calendar import departures
from homeassistant.components.gtfs.const import (
    CONF_DATABASE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import ATTR_ENTITY_ID, CONF_URL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    FEED_URL,
    ROUTE_ENTITY_ID,
    ROUTE_SUBENTRY_ID,
    TEST_DATABASE,
    build_feed_zip,
    setup_integration,
)

HEADSIGN_TRIPS = (
    "route_id,service_id,trip_id,trip_headsign\n"
    "R1,DAILY,T1,Airport\n"
    "R1,DAILY,T2,Airport\n"
    "N,DAILY,NT1,\n"
)


def _route_entry(
    *routes: tuple[str, str, str], pref_disable_polling: bool = False
) -> MockConfigEntry:
    """Return a feed entry with a route subentry for each (origin, destination, title)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Agency",
        data={CONF_URL: FEED_URL, CONF_DATABASE: TEST_DATABASE},
        pref_disable_polling=pref_disable_polling,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_ORIGIN: origin, CONF_DESTINATION: destination},
                subentry_id=f"route_{origin}_{destination}".lower(),
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=title,
                unique_id=json.dumps([origin, destination]),
            )
            for origin, destination, title in routes
        ],
    )


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_calendar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the route calendar entity and its device."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    assert (
        device := device_registry.async_get_device_by_identifier(
            (DOMAIN, ROUTE_SUBENTRY_ID), mock_config_entry.entry_id
        )
    ) is not None
    assert device.name == "First Street to Third Street"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.config_entry_id == mock_config_entry.entry_id
    assert device.config_subentry_id == ROUTE_SUBENTRY_ID


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_calendar_follows_departures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the state is on during a trip and moves to the next departure."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.state == STATE_OFF
    assert state.attributes["message"] == "1 to Third Street"
    assert state.attributes["start_time"] == "2026-10-19 08:00:00"

    freezer.move_to("2026-10-19 08:05:00-04:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.state == STATE_ON

    freezer.move_to("2026-10-19 08:21:00-04:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.state == STATE_OFF
    assert state.attributes["start_time"] == "2026-10-19 17:00:00"


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_get_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the route's departures in a window, including a removed service day."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: ROUTE_ENTITY_ID,
            EVENT_START_DATETIME: "2026-10-20T00:00:00-04:00",
            EVENT_END_DATETIME: "2026-10-22T00:00:00-04:00",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_calendar_without_departures(hass: HomeAssistant) -> None:
    """Test a route with no departures within a week is off without an event."""
    entry = _route_entry(("S3", "S1", "Third Street to First Street"))
    await setup_integration(hass, entry)

    assert (
        state := hass.states.get("calendar.third_street_to_first_street")
    ) is not None
    assert state.state == STATE_OFF
    assert "message" not in state.attributes


@pytest.mark.usefixtures("mock_feed_download")
@pytest.mark.parametrize(
    ("now", "route", "entity_id", "expected_state", "start_time"),
    [
        pytest.param(
            "2026-10-19 08:05:00-04:00",
            ("S1", "S3", "First Street to Third Street"),
            ROUTE_ENTITY_ID,
            STATE_ON,
            "2026-10-19 08:00:00",
            id="trip_in_progress",
        ),
        pytest.param(
            "2026-10-20 00:35:00-04:00",
            ("N1", "N2", "Night Depot to Night Terminal"),
            "calendar.night_depot_to_night_terminal",
            STATE_ON,
            "2026-10-20 00:30:00",
            id="overnight_trip_from_previous_service_day",
        ),
        pytest.param(
            "2026-10-19 18:00:00-04:00",
            ("S1", "S3", "First Street to Third Street"),
            ROUTE_ENTITY_ID,
            STATE_OFF,
            "2026-10-20 08:00:00",
            id="next_departure_tomorrow",
        ),
    ],
)
async def test_calendar_at_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    now: str,
    route: tuple[str, str, str],
    entity_id: str,
    expected_state: str,
    start_time: str,
) -> None:
    """Test the state and event found when the entry is set up."""
    freezer.move_to(now)
    await setup_integration(hass, _route_entry(route))

    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == expected_state
    assert state.attributes["start_time"] == start_time


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_calendar_steps_to_next_departure_without_polling(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the calendar's own alarms advance to the next cached departure."""
    entry = _route_entry(
        ("S1", "S3", "First Street to Third Street"), pref_disable_polling=True
    )
    await setup_integration(hass, entry)

    freezer.move_to("2026-10-19 08:21:00-04:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.state == STATE_OFF
    assert state.attributes["start_time"] == "2026-10-19 17:00:00"


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
@pytest.mark.parametrize(
    "feed_zip",
    [
        pytest.param(
            build_feed_zip(replace={"trips.txt": HEADSIGN_TRIPS}), id="headsign"
        )
    ],
)
async def test_trip_headsign_in_summary(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the trip's headsign replaces the destination name in the summary."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.attributes["message"] == "1 to Airport"


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_events_have_stable_uids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test each departure's uid names its trip and service day."""
    await setup_integration(hass, mock_config_entry)

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{ROUTE_ENTITY_ID}",
        params={
            "start": "2026-10-20T00:00:00-04:00",
            "end": "2026-10-22T00:00:00-04:00",
        },
    )

    assert response.status == 200
    assert [event["uid"] for event in await response.json()] == [
        "T1-2026-10-20",
        "T2-2026-10-20",
    ]


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_routes_share_a_feed(hass: HomeAssistant) -> None:
    """Test two routes of one feed each get their own calendar."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Agency",
        data={CONF_URL: FEED_URL, CONF_DATABASE: TEST_DATABASE},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_ORIGIN: "S1", CONF_DESTINATION: "S3"},
                subentry_id="route_s1_s3",
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title="First Street to Third Street",
                unique_id='["S1", "S3"]',
            ),
            ConfigSubentryDataWithId(
                data={CONF_ORIGIN: "S2", CONF_DESTINATION: "S3"},
                subentry_id="route_s2_s3",
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title="Second Street to Third Street",
                unique_id='["S2", "S3"]',
            ),
        ],
    )
    await setup_integration(hass, entry)

    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.attributes["start_time"] == "2026-10-19 08:00:00"
    assert (
        state := hass.states.get("calendar.second_street_to_third_street")
    ) is not None
    assert state.attributes["start_time"] == "2026-10-19 08:10:00"


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_route_with_stop_missing_from_feed(hass: HomeAssistant) -> None:
    """Test a route whose stop left the feed still gets a calendar."""
    entry = _route_entry(("S1", "GONE", "First Street to Gone"))
    await setup_integration(hass, entry)

    assert (state := hass.states.get("calendar.first_street_to_gone")) is not None
    assert state.state == STATE_OFF
    assert "message" not in state.attributes


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_calendar_polls_every_15_minutes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the static schedule is only searched again every 15 minutes."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.gtfs.calendar.departures", wraps=departures
    ) as mock_departures:
        freezer.tick(timedelta(minutes=14))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_departures.call_count == 0

        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_departures.call_count == 1
