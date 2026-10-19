"""Verify the calendar component works normally without alternate dates.

These tests drive the real ``local_calendar`` integration, which never produces
``alternate_dates``, through the real REST and WebSocket code paths. They prove
the calendar component is unchanged for integrations that do not opt in.
"""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.local_calendar.const import DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

# Reuse the local_calendar test fixtures so this regression test exercises the
# real integration without duplicating its store mocking.
from tests.components.local_calendar.conftest import (  # noqa: F401
    TEST_ENTITY,
    GetEventsFn,
    get_events_fixture,
    mock_config_entry,
    mock_store,
    mock_store_read_side_effect,
    setup_integration,
)
from tests.typing import WebSocketGenerator

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:plain-all-day
DTSTART;VALUE=DATE:20261015
DTEND;VALUE=DATE:20261016
SUMMARY:All Day Event
DESCRIPTION:An all day event
LOCATION:Somewhere
END:VEVENT
BEGIN:VEVENT
UID:plain-timed
DTSTART:20261016T090000Z
DTEND:20261016T100000Z
SUMMARY:Timed Event
DESCRIPTION:A timed event
LOCATION:Room A
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture(autouse=True)
def ics_content() -> str:
    """Return the ICS payload used by the fake store."""
    return ICS


def _range() -> tuple[str, str]:
    """Return a wide ISO range covering the fixture events."""
    start = dt_util.now() - timedelta(days=30)
    return start.isoformat(), (start + timedelta(days=365)).isoformat()


@pytest.mark.usefixtures("setup_integration")
async def test_rest_api_has_no_alternate_dates(get_events: GetEventsFn) -> None:
    """Test the REST API serves normal events with no alternate_dates key."""
    start, end = _range()
    events = await get_events(start, end)

    assert events, "local_calendar returned no events"
    for event in events:
        assert "alternate_dates" not in event
        assert event["summary"]


@pytest.mark.usefixtures("setup_integration")
async def test_rest_api_preserves_date_shapes(get_events: GetEventsFn) -> None:
    """Test all-day and timed events keep their original API date shapes."""
    start, end = _range()
    events = await get_events(start, end)
    by_summary = {event["summary"]: event for event in events}

    all_day = by_summary["All Day Event"]
    assert "date" in all_day["start"]
    assert "dateTime" not in all_day["start"]
    assert all_day["location"] == "Somewhere"
    assert all_day["description"] == "An all day event"

    timed = by_summary["Timed Event"]
    assert "dateTime" in timed["start"]
    assert "date" not in timed["start"]
    assert timed["location"] == "Room A"


@pytest.mark.usefixtures("setup_integration")
async def test_websocket_subscription_has_no_alternate_dates(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the WebSocket subscription streams events with no alternate_dates."""
    client = await hass_ws_client(hass)
    start, end = _range()

    await client.send_json_auto_id(
        {
            "type": "calendar/event/subscribe",
            "entity_id": TEST_ENTITY,
            "start": start,
            "end": end,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"

    events = msg["event"]["events"]
    assert events, "subscription returned no events"
    for event in events:
        assert "alternate_dates" not in event
        assert event["summary"]


@pytest.mark.usefixtures("setup_integration")
async def test_state_attributes_unchanged(hass: HomeAssistant) -> None:
    """Test entity state attributes keep their original shape."""
    state = hass.states.get(TEST_ENTITY)
    assert state is not None

    attributes = state.attributes
    assert "alternate_dates" not in attributes
    assert "supported_alternate_calendars" not in attributes
    assert attributes["supported_features"] == 7


async def test_state_attributes_of_active_event_unchanged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """Test an active event's attributes exclude alternate dates.

    ``state_attributes`` is only populated while an event is running, so time is
    frozen inside the all-day fixture event to pin the active-event attributes.
    """
    freezer.move_to("2026-10-15 12:00:00+00:00")
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY)
    assert state is not None
    assert state.state == STATE_ON, "expected an active event"

    attributes = state.attributes
    assert attributes["message"] == "All Day Event"
    assert attributes["location"] == "Somewhere"
    assert attributes["all_day"] is True
    assert "alternate_dates" not in attributes
    assert "supported_alternate_calendars" not in attributes
