"""Tests for the GTFS calendar."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
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
from homeassistant.helpers import entity_registry as er

from . import FEED_URL, ROUTE_ENTITY_ID, TEST_DATABASE, setup_integration


@pytest.mark.freeze_time("2026-10-19 07:30:00-04:00")
@pytest.mark.usefixtures("mock_feed_download")
async def test_calendar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the route calendar entity and its device."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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
async def test_calendar_without_departures(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a route with no departures within a week is off without an event."""
    mock_config_entry.add_to_hass(hass)
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={CONF_ORIGIN: "S3", CONF_DESTINATION: "S1"},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ROUTE_ENTITY_ID)) is not None
    assert state.state == STATE_OFF
    assert "message" not in state.attributes


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
