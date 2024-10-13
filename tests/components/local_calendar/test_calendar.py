"""Tests for calendar platform of local calendar."""

import datetime
import textwrap

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import DATE_STR_FORMAT
import homeassistant.util.dt as dt_util

from .conftest import (
    FRIENDLY_NAME,
    TEST_ENTITY,
    ClientFixture,
    GetEventsFn,
    event_fields,
)

from tests.common import MockConfigEntry


async def test_empty_calendar(
    hass: HomeAssistant, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test querying the API and fetching events."""
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert len(events) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
        "supported_features": 7,
    }


@pytest.mark.parametrize(
    ("dtstart", "dtend"),
    [
        ("1997-07-14T18:00:00+01:00", "1997-07-15T05:00:00+01:00"),
        ("1997-07-14T17:00:00+00:00", "1997-07-15T04:00:00+00:00"),
        ("1997-07-14T11:00:00-06:00", "1997-07-14T22:00:00-06:00"),
        ("1997-07-14T10:00:00-07:00", "1997-07-14T21:00:00-07:00"),
    ],
)
async def test_api_date_time_event(
    ws_client: ClientFixture,
    setup_integration: None,
    get_events: GetEventsFn,
    dtstart: str,
    dtend: str,
) -> None:
    """Test an event with a start/end date time.

    Events created in various timezones are ultimately returned relative
    to local home assistant timezone.
    """
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": dtstart,
                "dtend": dtend,
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

    # Query events in UTC

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

    # Query events overlapping with start and end but in another timezone
    events = await get_events("1997-07-12T23:00:00-01:00", "1997-07-14T17:00:00-01:00")
    assert len(events) == 1
    events = await get_events("1997-07-15T02:00:00-01:00", "1997-07-15T05:00:00-01:00")
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
    assert state
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
    assert state
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


async def test_websocket_delete_empty_recurrence_id(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test websocket delete command with an empty recurrence id no-op."""
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

    # Delete the event with an empty recurrence id
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "recurrence_id": "",
        },
    )
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert list(map(event_fields, events)) == []


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


async def test_websocket_update_empty_recurrence(
    ws_client: ClientFixture, setup_integration: None, get_events: GetEventsFn
) -> None:
    """Test an edit with an empty recurrence id (no-op)."""
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

    # Update the event with an empty string for the recurrence id which should
    # have no effect.
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": uid,
            "recurrence_id": "",
            "event": {
                "summary": "Bastille Day Party [To be rescheduled]",
                "dtstart": "1997-07-15T11:00:00-06:00",
                "dtend": "1997-07-15T22:00:00-06:00",
            },
        },
    )
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party [To be rescheduled]",
            "start": {"dateTime": "1997-07-15T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-15T22:00:00-06:00"},
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
            "recurrence_id": "20220824T083000",
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
    assert resp
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "invalid_format"


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
) -> None:
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
    assert result
    assert not result.get("success")
    assert "error" in result
    assert "code" in result["error"]
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
    assert result
    assert not result.get("success")
    assert "error" in result
    assert "code" in result["error"]
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
    assert result
    assert not result.get("success")
    assert "error" in result
    assert "code" in result["error"]
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
    assert result
    assert not result.get("success")
    assert "error" in result
    assert "code" in result["error"]
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
    assert resp
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "failed"


async def test_delete_invalid_event_id(
    ws_client: ClientFixture,
    setup_integration: None,
    hass: HomeAssistant,
) -> None:
    """Test deleting an event with an invalid event uid."""
    client = await ws_client()
    resp = await client.cmd(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "uid-does-not-exist",
        },
    )
    assert resp
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "failed"


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
            "location": "Test Location",
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
            "location": "Test Location",
        }
    ]

    events = await get_events("1997-07-13T00:00:00Z", "1997-07-14T18:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T22:00:00-06:00"},
            "location": "Test Location",
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
            "location": "Test Location",
        }
    ]


@pytest.mark.parametrize(
    "ics_content",
    [
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART:19970714
            DTEND:19970714
            END:VEVENT
            END:VCALENDAR
        """
        ),
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART:19970714
            DTEND:19970710
            END:VEVENT
            END:VCALENDAR
        """
        ),
    ],
    ids=["no_duration", "negative"],
)
async def test_invalid_all_day_event(
    ws_client: ClientFixture,
    setup_integration: None,
    get_events: GetEventsFn,
) -> None:
    """Test all day events with invalid durations, which are coerced to be valid."""
    events = await get_events("1997-07-14T00:00:00Z", "1997-07-16T00:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"date": "1997-07-14"},
            "end": {"date": "1997-07-15"},
        }
    ]


@pytest.mark.parametrize(
    "ics_content",
    [
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART:19970714T110000
            DTEND:19970714T110000
            END:VEVENT
            END:VCALENDAR
        """
        ),
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART:19970714T110000
            DTEND:19970710T100000
            END:VEVENT
            END:VCALENDAR
        """
        ),
    ],
    ids=["no_duration", "negative"],
)
async def test_invalid_event_duration(
    ws_client: ClientFixture,
    setup_integration: None,
    get_events: GetEventsFn,
) -> None:
    """Test events with invalid durations, which are coerced to be valid."""
    events = await get_events("1997-07-14T00:00:00Z", "1997-07-16T00:00:00Z")
    assert list(map(event_fields, events)) == [
        {
            "summary": "Bastille Day Party",
            "start": {"dateTime": "1997-07-14T11:00:00-06:00"},
            "end": {"dateTime": "1997-07-14T11:30:00-06:00"},
        }
    ]
