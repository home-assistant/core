"""Tests for calendar platform of local calendar."""

from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import patch
import urllib

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.local_calendar import LocalCalendarStore
from homeassistant.components.local_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

CALENDAR_NAME = "Light Schedule"
FRIENDLY_NAME = "Light schedule"
TEST_ENTITY = "calendar.light_schedule"


class FakeStore(LocalCalendarStore):
    """Mock storage implementation."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize FakeStore."""
        super().__init__(hass, path)
        self._content = ""

    def _load(self) -> str:
        """Read from calendar storage."""
        return self._content

    def _store(self, ics_content: str) -> None:
        """Persist the calendar storage."""
        self._content = ics_content


@pytest.fixture(name="store", autouse=True)
def mock_store() -> None:
    """Test cleanup, remove any media storage persisted during the test."""

    stores: dict[Path, FakeStore] = {}

    def new_store(hass: HomeAssistant, path: Path) -> FakeStore:
        if path not in stores:
            stores[path] = FakeStore(hass, path)
        return stores[path]

    with patch(
        "homeassistant.components.local_calendar.LocalCalendarStore", new=new_store
    ):
        yield


@pytest.fixture(name="time_zone")
def mock_time_zone() -> str:
    """Fixture for time zone to use in tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    return "America/Regina"


@pytest.fixture(autouse=True)
def set_time_zone(hass: HomeAssistant, time_zone: str):
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    hass.config.set_time_zone(time_zone)


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for mock configuration entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_CALENDAR_NAME: CALENDAR_NAME})


@pytest.fixture(name="setup_integration")
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


GetEventsFn = Callable[[str, str], Awaitable[dict[str, Any]]]


@pytest.fixture(name="get_events")
def get_events_fixture(hass_client: ClientSessionGenerator) -> GetEventsFn:
    """Fetch calendar events from the HTTP API."""

    async def _fetch(start: str, end: str) -> None:
        client = await hass_client()
        response = await client.get(
            f"/api/calendars/{TEST_ENTITY}?start={urllib.parse.quote(start)}&end={urllib.parse.quote(end)}"
        )
        assert response.status == HTTPStatus.OK
        return await response.json()

    return _fetch


def event_fields(data: dict[str, str]) -> dict[str, str]:
    """Filter event API response to minimum fields."""
    return {
        k: data.get(k)
        for k in ["summary", "start", "end", "recurrence_id"]
        if data.get(k)
    }


class Client:
    """Test client with helper methods for calendar websocket."""

    def __init__(self, client):
        """Initialize Client."""
        self.client = client
        self.id = 0

    async def cmd(self, cmd: str, payload: dict[str, Any] = None) -> dict[str, Any]:
        """Send a command and receive the json result."""
        self.id += 1
        await self.client.send_json(
            {
                "id": self.id,
                "type": f"calendar/event/{cmd}",
                **(payload if payload is not None else {}),
            }
        )
        resp = await self.client.receive_json()
        assert resp.get("id") == self.id
        return resp

    async def cmd_result(self, cmd: str, payload: dict[str, Any] = None) -> Any:
        """Send a command and parse the result."""
        resp = await self.cmd(cmd, payload)
        assert resp.get("success")
        assert resp.get("type") == "result"
        return resp.get("result")


ClientFixture = Callable[[], Awaitable[Client]]


@pytest.fixture
async def ws_client(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> ClientFixture:
    """Fixture for creating the test websocket client."""

    async def create_client() -> Client:
        ws_client = await hass_ws_client(hass)
        return Client(ws_client)

    return create_client


async def test_empty_calendar(
    hass: HomeAssistant, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test querying the API and fetching events."""
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert len(events) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
        "supported_features": 7,
    }


async def test_api_date_time_event(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test an event with a start/end date time."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": "1997-07-14T17:00:00+00:00",
                "dtend": "1997-07-15T04:00:00+00:00",
            },
        },
    )

    events = await get_events("1997-07-14T00:00:00Z", "1997-07-16T00:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
        }
    ]

    # Time range before event
    events = await get_events("1997-07-13T00:00:00Z", "1997-07-14T16:00:00Z")
    assert len(events) == 0
    # Time range after event
    events = await get_events("1997-07-15T05:00:00Z", "1997-07-15T06:00:00Z")
    assert len(events) == 0

    # Overlap with event start
    events = await get_events("1997-07-13T00:00:00Z", "1997-07-14T18:00:00Z")
    assert len(events) == 1
    # Overlap with event end
    events = await get_events("1997-07-15T03:00:00Z", "1997-07-15T06:00:00Z")
    assert len(events) == 1


async def test_api_date_event(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test an event with a start/end date all day event."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Festival International de Jazz de Montreal",
                "dtstart": "2007-06-28",
                "dtend": "2007-07-09",
            },
        },
    )

    events = await get_events("2007-06-20T00:00:00", "2007-07-20T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Festival International de Jazz de Montreal",
            "start": {"date": "2007-06-28"},
            "end": {"date": "2007-07-09"},
        }
    ]

    # Time range before event (timezone is -6)
    events = await get_events("2007-06-26T00:00:00Z", "2007-06-28T01:00:00Z")
    assert len(events) == 0
    # Time range after event
    events = await get_events("2007-07-10T00:00:00Z", "2007-07-11T00:00:00Z")
    assert len(events) == 0

    # Overlap with event start (timezone is -6)
    events = await get_events("2007-06-26T00:00:00Z", "2007-06-28T08:00:00Z")
    assert len(events) == 1
    # Overlap with event end
    events = await get_events("2007-07-09T00:00:00Z", "2007-07-11T00:00:00Z")
    assert len(events) == 1


async def test_active_event(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    setup_integration: None,
) -> None:
    """Test an event with a start/end date time."""
    start = dt_util.now() - datetime.timedelta(minutes=30)
    end = dt_util.now() + datetime.timedelta(minutes=30)
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Evening lights",
                "dtstart": start.isoformat(),
                "dtend": end.isoformat(),
            },
        },
    )

    state = hass.states.get(TEST_ENTITY)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
        "message": "Evening lights",
        "all_day": False,
        "description": "",
        "location": "",
        "start_time": start.strftime(DATE_STR_FORMAT),
        "end_time": end.strftime(DATE_STR_FORMAT),
        "supported_features": 7,
    }


async def test_upcoming_event(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    setup_integration: None,
) -> None:
    """Test an event with a start/end date time."""
    start = dt_util.now() + datetime.timedelta(days=1)
    end = dt_util.now() + datetime.timedelta(days=1, hours=1)
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Evening lights",
                "dtstart": start.isoformat(),
                "dtend": end.isoformat(),
            },
        },
    )

    state = hass.states.get(TEST_ENTITY)
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
        "message": "Evening lights",
        "all_day": False,
        "description": "",
        "location": "",
        "start_time": start.strftime(DATE_STR_FORMAT),
        "end_time": end.strftime(DATE_STR_FORMAT),
        "supported_features": 7,
    }


async def test_recurring_event(
    ws_client: ClientFixture,
    setup_integration: None,
    hass: HomeAssistant,
    get_events: GetEventsFn,
) -> None:
    """Test an event with a recurrence rule."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Monday meeting",
                "dtstart": "2022-08-29T09:00:00",
                "dtend": "2022-08-29T10:00:00",
                "rrule": "FREQ=WEEKLY",
            },
        },
    )

    events = await get_events("2022-08-20T00:00:00", "2022-09-20T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Monday meeting",
            "start": {"dateTime": "2022-08-29T09:00:00-06:00"},
            "end": {"dateTime": "2022-08-29T10:00:00-06:00"},
            "recurrence_id": "20220829T090000",
        },
        {
            "summary": "Monday meeting",
            "start": {"dateTime": "2022-09-05T09:00:00-06:00"},
            "end": {"dateTime": "2022-09-05T10:00:00-06:00"},
            "recurrence_id": "20220905T090000",
        },
        {
            "summary": "Monday meeting",
            "start": {"dateTime": "2022-09-12T09:00:00-06:00"},
            "end": {"dateTime": "2022-09-12T10:00:00-06:00"},
            "recurrence_id": "20220912T090000",
        },
        {
            "summary": "Monday meeting",
            "start": {"dateTime": "2022-09-19T09:00:00-06:00"},
            "end": {"dateTime": "2022-09-19T10:00:00-06:00"},
            "recurrence_id": "20220919T090000",
        },
    ]


async def test_websocket_delete(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test websocket delete command."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": "1997-07-14T17:00:00+00:00",
                "dtend": "1997-07-15T04:00:00+00:00",
            },
        },
    )

    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
        }
    ]
    uid = events[0]["uid"]

    # Delete the event
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
        },
    )
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert list(map(event_fields, events)) == []


async def test_websocket_delete_recurring(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test deleting a recurring event."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Morning Routine",
                "dtstart": "2022-08-22T08:30:00",
                "dtend": "2022-08-22T09:00:00",
                "rrule": "FREQ=DAILY",
            },
        },
    )

    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-23T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-23T09:00:00-06:00"},
            "recurrence_id": "20220823T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-24T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-24T09:00:00-06:00"},
            "recurrence_id": "20220824T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-25T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-25T09:00:00-06:00"},
            "recurrence_id": "20220825T083000",
        },
    ]
    uid = events[0]["uid"]
    assert [event["uid"] for event in events] == [uid] * 4

    # Cancel a single instance and confirm it was removed
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "recurrence_id": "20220824T083000",
        },
    )
    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-23T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-23T09:00:00-06:00"},
            "recurrence_id": "20220823T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-25T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-25T09:00:00-06:00"},
            "recurrence_id": "20220825T083000",
        },
    ]

    # Delete all and future and confirm multiple were removed
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "recurrence_id": "20220823T083000",
            "recurrence_range": "THISANDFUTURE",
        },
    )
    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
    ]


async def test_websocket_update(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test websocket update command."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": "1997-07-14T17:00:00+00:00",
                "dtend": "1997-07-15T04:00:00+00:00",
            },
        },
    )

    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
        }
    ]
    uid = events[0]["uid"]

    # Update the event
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "event": {
                "summary": "Bastille Day Party [To be rescheduled]",
                "dtstart": "1997-07-14",
                "dtend": "1997-07-15",
            },
        },
    )
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party [To be rescheduled]",
            "start": {"date": "1997-07-14"},
            "end": {"date": "1997-07-15"},
        }
    ]


async def test_websocket_update_recurring_this_and_future(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test updating a recurring event."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Morning Routine",
                "dtstart": "2022-08-22T08:30:00",
                "dtend": "2022-08-22T09:00:00",
                "rrule": "FREQ=DAILY",
            },
        },
    )

    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-23T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-23T09:00:00-06:00"},
            "recurrence_id": "20220823T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-24T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-24T09:00:00-06:00"},
            "recurrence_id": "20220824T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-25T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-25T09:00:00-06:00"},
            "recurrence_id": "20220825T083000",
        },
    ]
    uid = events[0]["uid"]
    assert [event["uid"] for event in events] == [uid] * 4

    # Update a single instance and confirm the change is reflected
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "recurrence_id": "20220824T083000",
            "recurrence_range": "THISANDFUTURE",
            "event": {
                "summary": "Morning Routine [Adjusted]",
                "dtstart": "2022-08-24T08:00:00",
                "dtend": "2022-08-24T08:30:00",
            },
        },
    )
    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-23T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-23T09:00:00-06:00"},
            "recurrence_id": "20220823T083000",
        },
        {
            "summary": "Morning Routine [Adjusted]",
            "start": {"dateTime": "2022-08-24T08:00:00-06:00"},
            "end": {"dateTime": "2022-08-24T08:30:00-06:00"},
            "recurrence_id": "20220824T080000",
        },
        {
            "summary": "Morning Routine [Adjusted]",
            "start": {"dateTime": "2022-08-25T08:00:00-06:00"},
            "end": {"dateTime": "2022-08-25T08:30:00-06:00"},
            "recurrence_id": "20220825T080000",
        },
    ]


async def test_websocket_update_recurring(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test updating a recurring event."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Morning Routine",
                "dtstart": "2022-08-22T08:30:00",
                "dtend": "2022-08-22T09:00:00",
                "rrule": "FREQ=DAILY",
            },
        },
    )

    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-23T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-23T09:00:00-06:00"},
            "recurrence_id": "20220823T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-24T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-24T09:00:00-06:00"},
            "recurrence_id": "20220824T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-25T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-25T09:00:00-06:00"},
            "recurrence_id": "20220825T083000",
        },
    ]
    uid = events[0]["uid"]
    assert [event["uid"] for event in events] == [uid] * 4

    # Update a single instance and confirm the change is reflected
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "recurrence_id": "20220824T083000",
            "event": {
                "summary": "Morning Routine [Adjusted]",
                "dtstart": "2022-08-24T08:00:00",
                "dtend": "2022-08-24T08:30:00",
            },
        },
    )
    events = await get_events("2022-08-22T00:00:00", "2022-08-26T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-22T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-22T09:00:00-06:00"},
            "recurrence_id": "20220822T083000",
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-23T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-23T09:00:00-06:00"},
            "recurrence_id": "20220823T083000",
        },
        {
            "summary": "Morning Routine [Adjusted]",
            "start": {"dateTime": "2022-08-24T08:00:00-06:00"},
            "end": {"dateTime": "2022-08-24T08:30:00-06:00"},
        },
        {
            "summary": "Morning Routine",
            "start": {"dateTime": "2022-08-25T08:30:00-06:00"},
            "end": {"dateTime": "2022-08-25T09:00:00-06:00"},
            "recurrence_id": "20220825T083000",
        },
    ]


@pytest.mark.parametrize(
    "rrule",
    [
        "FREQ=SECONDLY",
        "FREQ=MINUTELY",
        "FREQ=HOURLY",
        "invalid",
        "",
    ],
)
async def test_invalid_rrule(
    ws_client: ClientFixture,
    setup_integration: None,
    hass: HomeAssistant,
    get_events: GetEventsFn,
    rrule: str,
) -> None:
    """Test an event with a recurrence rule."""
    client = await ws_client()
    resp = await client.cmd(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Monday meeting",
                "dtstart": "2022-08-29T09:00:00",
                "dtend": "2022-08-29T10:00:00",
                "rrule": rrule,
            },
        },
    )
    assert not resp.get("success")
    assert "error" in resp
    assert resp.get("error").get("code") == "invalid_format"


@pytest.mark.parametrize(
    ("time_zone", "event_order"),
    [
        ("America/Los_Angeles", ["One", "Two", "All Day Event"]),
        ("America/Regina", ["One", "Two", "All Day Event"]),
        ("UTC", ["One", "All Day Event", "Two"]),
        ("Asia/Tokyo", ["All Day Event", "One", "Two"]),
    ],
)
async def test_all_day_iter_order(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    setup_integration: None,
    get_events: GetEventsFn,
    event_order: list[str],
):
    """Test the sort order of an all day events depending on the time zone."""
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "All Day Event",
                "dtstart": "2022-10-08",
                "dtend": "2022-10-09",
            },
        },
    )
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "One",
                "dtstart": "2022-10-07T23:00:00+00:00",
                "dtend": "2022-10-07T23:30:00+00:00",
            },
        },
    )
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Two",
                "dtstart": "2022-10-08T01:00:00+00:00",
                "dtend": "2022-10-08T02:00:00+00:00",
            },
        },
    )

    events = await get_events("2022-10-06T00:00:00Z", "2022-10-09T00:00:00Z")
    assert [event["summary"] for event in events] == event_order


async def test_start_end_types(
    ws_client: ClientFixture,
    setup_integration: None,
) -> None:
    """Test a start and end with different date and date time types."""
    client = await ws_client()
    result = await client.cmd(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": "1997-07-15",
                "dtend": "1997-07-14T17:00:00+00:00",
            },
        },
    )
    assert not result.get("success")
    assert "error" in result
    assert "code" in result.get("error")
    assert result["error"]["code"] == "invalid_format"


async def test_end_before_start(
    ws_client: ClientFixture,
    setup_integration: None,
) -> None:
    """Test an event with a start/end date time."""
    client = await ws_client()
    result = await client.cmd(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": "1997-07-15T04:00:00+00:00",
                "dtend": "1997-07-14T17:00:00+00:00",
            },
        },
    )
    assert not result.get("success")
    assert "error" in result
    assert "code" in result.get("error")
    assert result["error"]["code"] == "invalid_format"


async def test_invalid_recurrence_rule(
    ws_client: ClientFixture,
    setup_integration: None,
) -> None:
    """Test an event with a recurrence rule."""
    client = await ws_client()
    result = await client.cmd(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Monday meeting",
                "dtstart": "2022-08-29T09:00:00",
                "dtend": "2022-08-29T10:00:00",
                "rrule": "FREQ=invalid;'",
            },
        },
    )
    assert not result.get("success")
    assert "error" in result
    assert "code" in result.get("error")
    assert result["error"]["code"] == "invalid_format"


async def test_invalid_date_formats(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Exercises a validation error within rfc5545 parsing in ical."""
    client = await ws_client()
    result = await client.cmd(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                # Can't mix offset aware and floating dates
                "dtstart": "1997-07-15T04:00:00+08:00",
                "dtend": "1997-07-14T17:00:00",
            },
        },
    )
    assert not result.get("success")
    assert "error" in result
    assert "code" in result.get("error")
    assert result["error"]["code"] == "invalid_format"


async def test_update_invalid_event_id(
    ws_client: ClientFixture,
    setup_integration: None,
    hass: HomeAssistant,
) -> None:
    """Test updating an event with an invalid event uid."""
    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "uid-does-not-exist",
            "event": {
                "summary": "Bastille Day Party [To be rescheduled]",
                "dtstart": "1997-07-14",
                "dtend": "1997-07-15",
            },
        },
    )
    assert not resp.get("success")
    assert "error" in resp
    assert resp.get("error").get("code") == "failed"


@pytest.mark.parametrize(
    ("start_date_time", "end_date_time"),
    [
        ("1997-07-14T17:00:00+00:00", "1997-07-15T04:00:00+00:00"),
        ("1997-07-14T11:00:00-06:00", "1997-07-14T22:00:00-06:00"),
    ],
)
async def test_create_event_service(
    hass: HomeAssistant,
    setup_integration: None,
    get_events: GetEventsFn,
    start_date_time: str,
    end_date_time: str,
    config_entry: MockConfigEntry,
) -> None:
    """Test creating an event using the create_event service."""

    await hass.services.async_call(
        "calendar",
        "create_event",
        {
            "start_date_time": start_date_time,
            "end_date_time": end_date_time,
            "summary": "Bastille Day Party",
        },
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )
    # Ensure data is written to disk
    await hass.async_block_till_done()

    events = await get_events("1997-07-14T00:00:00Z", "1997-07-16T00:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
        }
    ]

    events = await get_events("1997-07-13T00:00:00Z", "1997-07-14T18:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
        }
    ]

    # Reload the config entry, which reloads the content from the store and
    # verifies that the persisted data can be parsed correctly.
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    events = await get_events("1997-07-13T00:00:00Z", "1997-07-14T18:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
        }
    ]
