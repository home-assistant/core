"""Tests for calendar platform of Remote Calendar."""

from datetime import datetime
import pathlib
import textwrap

from httpx import Response
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import (
    CALENDER_URL,
    FRIENDLY_NAME,
    TEST_ENTITY,
    GetEventsFn,
    event_fields,
)

from tests.common import MockConfigEntry

# Test data files with known calendars from various sources. You can add a new file
# in the testdata directory and add it will be parsed and tested.
TESTDATA_FILES = sorted(
    pathlib.Path("tests/components/remote_calendar/testdata/").glob("*.ics")
)
TESTDATA_IDS = [f.stem for f in TESTDATA_FILES]


@respx.mock
async def test_empty_calendar(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    get_events: GetEventsFn,
) -> None:
    """Test querying the API and fetching events."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """BEGIN:VCALENDAR
                VERSION:2.0
                PRODID:-//hacksw/handcal//NONSGML v1.0//EN
                END:VCALENDAR
            """
            ),
        )
    )
    await setup_integration(hass, config_entry)
    events = await get_events("1997-07-14T00:00:00", "1997-07-16T00:00:00")
    assert len(events) == 0

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
    }


@pytest.mark.parametrize(
    "ics_content",
    [
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            VERSION:2.0
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART;TZID=Europe/Berlin:19970714T190000
            DTEND;TZID=Europe/Berlin:19970715T060000
            END:VEVENT
            END:VCALENDAR
            """
        ),
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART:19970714T170000Z
            DTEND:19970715T040000Z
            END:VEVENT
            END:VCALENDAR
            """
        ),
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            VERSION:2.0
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART;TZID=America/Regina:19970714T110000
            DTEND;TZID=America/Regina:19970714T220000
            END:VEVENT
            END:VCALENDAR
            """
        ),
        textwrap.dedent(
            """\
            BEGIN:VCALENDAR
            VERSION:2.0
            BEGIN:VEVENT
            SUMMARY:Bastille Day Party
            DTSTART;TZID=America/Los_Angeles:19970714T100000
            DTEND;TZID=America/Los_Angeles:19970714T210000
            END:VEVENT
            END:VCALENDAR
            """
        ),
    ],
)
@respx.mock
async def test_api_date_time_event(
    get_events: GetEventsFn,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ics_content: str,
) -> None:
    """Test an event with a start/end date time."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    await setup_integration(hass, config_entry)
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


@respx.mock
async def test_api_date_event(
    get_events: GetEventsFn,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test an event with a start/end date all day event."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """\
            BEGIN:VCALENDAR
            VERSION:2.0
            BEGIN:VEVENT
            SUMMARY:Festival International de Jazz de Montreal
            DTSTART:20070628
            DTEND:20070709
            END:VEVENT
            END:VCALENDAR
            """
            ),
        )
    )
    await setup_integration(hass, config_entry)
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


@pytest.mark.freeze_time(datetime(2007, 6, 28, 12))
@respx.mock
async def test_active_event(
    get_events: GetEventsFn,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test an event with a start/end date time."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """\
            BEGIN:VCALENDAR
            VERSION:2.0
            BEGIN:VEVENT
            SUMMARY:Festival International de Jazz de Montreal
            LOCATION:Montreal
            DTSTART:20070628
            DTEND:20070709
            END:VEVENT
            END:VCALENDAR
            """
            ),
        )
    )
    await setup_integration(hass, config_entry)
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
        "message": "Festival International de Jazz de Montreal",
        "all_day": True,
        "description": "",
        "location": "Montreal",
        "start_time": "2007-06-28 00:00:00",
        "end_time": "2007-07-09 00:00:00",
    }


@pytest.mark.freeze_time(datetime(2007, 6, 27, 12))
@respx.mock
async def test_upcoming_event(
    get_events: GetEventsFn,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test an event with a start/end date time."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """\
            BEGIN:VCALENDAR
            VERSION:2.0
            BEGIN:VEVENT
            SUMMARY:Festival International de Jazz de Montreal
            LOCATION:Montreal
            DTSTART:20070628
            DTEND:20070709
            END:VEVENT
            END:VCALENDAR
            """
            ),
        )
    )
    await setup_integration(hass, config_entry)
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == FRIENDLY_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": FRIENDLY_NAME,
        "message": "Festival International de Jazz de Montreal",
        "all_day": True,
        "description": "",
        "location": "Montreal",
        "start_time": "2007-06-28 00:00:00",
        "end_time": "2007-07-09 00:00:00",
    }


@respx.mock
async def test_recurring_event(
    get_events: GetEventsFn,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test an event with a recurrence rule."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """\
            BEGIN:VCALENDAR
            BEGIN:VEVENT
            DTSTART:20220829T090000
            DTEND:20220829T100000
            SUMMARY:Monday meeting
            RRULE:FREQ=WEEKLY;BYDAY=MO
            END:VEVENT
            END:VCALENDAR
            """
            ),
        )
    )
    await setup_integration(hass, config_entry)

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


@respx.mock
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
    get_events: GetEventsFn,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    event_order: list[str],
) -> None:
    """Test the sort order of an all day events depending on the time zone."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=textwrap.dedent(
                """\
            BEGIN:VCALENDAR

            BEGIN:VEVENT
            DTSTART:20221008
            DTEND:20221009
            SUMMARY:All Day Event
            END:VEVENT

            BEGIN:VEVENT
            DTSTART:20221007T230000Z
            DTEND:20221008T233000Z
            SUMMARY:One
            END:VEVENT

            BEGIN:VEVENT
            DTSTART:20221008T010000Z
            DTEND:20221008T020000Z
            SUMMARY:Two
            END:VEVENT

            END:VCALENDAR
            """
            ),
        )
    )
    await setup_integration(hass, config_entry)

    events = await get_events("2022-10-06T00:00:00Z", "2022-10-09T00:00:00Z")
    assert [event["summary"] for event in events] == event_order


@respx.mock
@pytest.mark.parametrize("ics_filename", TESTDATA_FILES, ids=TESTDATA_IDS)
async def test_calendar_examples(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    get_events: GetEventsFn,
    ics_filename: pathlib.Path,
    snapshot: SnapshotAssertion,
) -> None:
    """Test parsing known calendars form test data files."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_filename.read_text(),
        )
    )
    await setup_integration(hass, config_entry)
    events = await get_events("1997-07-14T00:00:00", "2025-07-01T00:00:00")
    assert events == snapshot
