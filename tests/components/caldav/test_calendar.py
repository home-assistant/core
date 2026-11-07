"""The tests for the webdav calendar component."""

import asyncio
from collections.abc import Awaitable, Callable
import datetime as dt
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, Mock, patch
import zoneinfo

from caldav.calendarobjectresource import Event
from caldav.elements import cdav, dav, ical
from caldav.elements.base import BaseElement
from caldav.lib.error import DAVError, NotFoundError
from caldav.lib.http_sync import requests as caldav_requests
from caldav.lib.url import URL
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.caldav.api import async_get_calendars
from homeassistant.components.caldav.const import DOMAIN
from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    CalendarEntityFeature,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

EVENTS = [
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
SUMMARY:This is a normal event
LOCATION:Hamburg
DESCRIPTION:Surprisingly rainy
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Dynamics.//CalDAV Client//EN
BEGIN:VEVENT
UID:2
DTSTAMP:20171125T000000Z
DTSTART:20171127T100000Z
DTEND:20171127T110000Z
SUMMARY:This is an offset event !!-02:00
LOCATION:Hamburg
DESCRIPTION:Surprisingly shiny
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:3
DTSTAMP:20171125T000000Z
DTSTART:20171127
DTEND:20171128
SUMMARY:This is an all day event
LOCATION:Hamburg
DESCRIPTION:What a beautiful day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:4
DTSTAMP:20171125T000000Z
DTSTART:20171127
SUMMARY:This is an event without dtend or duration
LOCATION:Hamburg
DESCRIPTION:What an endless day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:5
DTSTAMP:20171125T000000Z
DTSTART:20171127
DURATION:PT1H
SUMMARY:This is an event with duration
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:6
DTSTAMP:20171125T000000Z
DTSTART:20171127T100000Z
DURATION:PT1H
SUMMARY:This is an event with duration
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:7
DTSTART;TZID=America/Los_Angeles:20171127T083000
DTSTAMP:20180301T020053Z
DTEND;TZID=America/Los_Angeles:20171127T093000
SUMMARY:Enjoy the sun
LOCATION:San Francisco
DESCRIPTION:Sunny day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:8
DTSTART:20171127T190000
DTEND:20171127T200000
SUMMARY:This is a floating Event
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:9
DTSTAMP:20171125T000000Z
DTSTART:20171027T220000Z
DTEND:20171027T223000Z
SUMMARY:This is a recurring event
LOCATION:Hamburg
DESCRIPTION:Every day for a while
RRULE:FREQ=DAILY;UNTIL=20171227T215959
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:10
DTSTAMP:20171125T000000Z
DTSTART:20171027T230000Z
DURATION:PT30M
SUMMARY:This is a recurring event with a duration
LOCATION:Hamburg
DESCRIPTION:Every day for a while as well
RRULE:FREQ=DAILY;UNTIL=20171227T215959
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:11
DTSTAMP:20171125T000000Z
DTSTART:20171027T233000Z
DTEND:20171027T235959Z
SUMMARY:This is a recurring event that has ended
LOCATION:Hamburg
DESCRIPTION:Every day for a while
RRULE:FREQ=DAILY;UNTIL=20171127T225959
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:12
DTSTAMP:20171125T000000Z
DTSTART:20171027T234500Z
DTEND:20171027T235959Z
SUMMARY:This is a recurring event that never ends
LOCATION:Hamburg
DESCRIPTION:Every day forever
RRULE:FREQ=DAILY
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:13
DTSTAMP:20161125T000000Z
DTSTART:20161127
DTEND:20161128
SUMMARY:This is a recurring all day event
LOCATION:Hamburg
DESCRIPTION:Groundhog Day
RRULE:FREQ=DAILY;COUNT=100
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:14
DTSTAMP:20151125T000000Z
DTSTART:20151127T000000Z
DTEND:20151127T003000Z
SUMMARY:This is an hourly recurring event
LOCATION:Hamburg
DESCRIPTION:The bell tolls for thee
RRULE:FREQ=HOURLY;INTERVAL=1;COUNT=12
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:14
DTSTAMP:20151125T000000Z
DTSTART:20151127T000000Z
DTEND:20151127T003000Z
RRULE:FREQ=HOURLY;INTERVAL=1;COUNT=12
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VTIMEZONE
TZID:Europe/London
BEGIN:STANDARD
DTSTART:19961027T020000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
TZNAME:GMT
TZOFFSETFROM:+0100
TZOFFSETTO:+0000
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19810329T010000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
TZNAME:BST
TZOFFSETFROM:+0000
TZOFFSETTO:+0100
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:15
DTSTAMP:20221125T000000Z
DTSTART;TZID=Europe/London:20221127T000000
DTEND;TZID=Europe/London:20221127T003000
SUMMARY:Event with a provided Timezone
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:16
DTSTAMP:20171125T000000Z
DTSTART:20171127
DTEND:20171128
SUMMARY:All day event with same start and end
LOCATION:Hamburg
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:17
DTSTAMP:20171125T000000Z
DTSTART:20171127T010000
DTEND:20171127T010000
SUMMARY:Event with no duration
LOCATION:Hamburg
END:VEVENT
END:VCALENDAR
""",
]

CALDAV_CONFIG = {
    "platform": "caldav",
    "url": "http://test.local",
    "custom_calendars": [],
}
UTC = "UTC"
AMERICA_NEW_YORK = "America/New_York"
ASIA_BAGHDAD = "Asia/Baghdad"

TEST_ENTITY = "calendar.example"
CALENDAR_NAME = "Example"
SUPPORTED_FEATURES = (
    CalendarEntityFeature.CREATE_EVENT
    | CalendarEntityFeature.DELETE_EVENT
    | CalendarEntityFeature.UPDATE_EVENT
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up config entry platforms."""
    return [Platform.CALENDAR]


@pytest.fixture(name="tz")
def mock_tz() -> str | None:
    """Fixture to specify the Home Assistant timezone to use during the test."""
    return None


@pytest.fixture(autouse=True)
async def set_tz(hass: HomeAssistant, tz: str | None) -> None:
    """Fixture to set the default TZ to the one requested."""
    if tz is not None:
        await hass.config.async_set_time_zone(tz)


@pytest.fixture(autouse=True)
def mock_http(hass: HomeAssistant) -> None:
    """Mock the http component."""
    hass.http = Mock()


@pytest.fixture(name="calendar_names")
def mock_calendar_names() -> list[str]:
    """Fixture to provide calendars returned by CalDAV client."""
    return ["Example"]


@pytest.fixture(name="calendars")
def mock_calendars(calendar_names: list[str]) -> list[Mock]:
    """Fixture to provide calendars returned by CalDAV client."""
    return [_mock_calendar(name) for name in calendar_names]


@pytest.fixture
def get_api_events(
    hass_client: ClientSessionGenerator,
) -> Callable[[str], Awaitable[dict[str, Any]]]:
    """Fixture to return events for a specific calendar using the API."""

    async def api_call(entity_id: str) -> dict[str, Any]:
        client = await hass_client()
        response = await client.get(
            # The start/end times are arbitrary since they are
            # ignored by `_mock_calendar` which just returns all
            # events for the calendar.
            f"/api/calendars/{entity_id}?start=2022-01-01&end=2022-01-01"
        )
        assert response.status == HTTPStatus.OK
        return await response.json()

    return api_call


def _local_datetime(hours: int, minutes: int) -> dt.datetime:
    """Build a datetime object for testing in the correct timezone."""
    return dt_util.as_local(dt.datetime(2017, 11, 27, hours, minutes, 0))


def _mock_calendar(
    name: str,
    supported_components: list[str] | None = None,
    color: str | Exception | None = None,
) -> Mock:
    calendar = Mock()
    calendar.client = None
    calendar.url = URL("http://test.local/calendar/")
    events = []
    for idx, event in enumerate(EVENTS):
        events.append(Event(None, f"{idx}.ics", event, calendar, str(idx)))
    if supported_components is None:
        supported_components = ["VEVENT"]
    calendar.search = MagicMock(return_value=events)
    calendar.get_display_name = MagicMock(return_value=name)
    calendar.get_supported_components = MagicMock(return_value=supported_components)

    def get_property(prop: BaseElement) -> str | None:
        if prop.tag != ical.CalendarColor.tag:
            return None
        if isinstance(color, Exception):
            raise color
        return color

    calendar.get_property = MagicMock(side_effect=get_property)
    return calendar


async def _get_api_events_for_vevent(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    vevent: str,
    uid: str,
) -> list[dict[str, Any]]:
    """Set up a calendar holding a single VEVENT and return its events from the API.

    Used by tests that assert on how one specific VEVENT property is parsed,
    which the shared EVENTS series cannot express: it is fixed at 18 entries
    that other tests count on.
    """
    calendar = Mock()
    calendar.client = None
    calendar.url = URL("http://test.local/calendar/")
    calendar.get_display_name = MagicMock(return_value="Example")
    calendar.get_supported_components = MagicMock(return_value=["VEVENT"])
    calendar.search = MagicMock(
        return_value=[Event(None, "0.ics", vevent, calendar, uid)]
    )

    with patch("homeassistant.components.caldav.calendar.DAVClient") as mock_client:
        mock_client.return_value.get_principal.return_value.get_calendars.return_value = [
            calendar
        ]
        assert await async_setup_component(
            hass, "calendar", {"calendar": CALDAV_CONFIG}
        )
        await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{TEST_ENTITY}?start=2017-11-27&end=2017-11-28"
    )
    assert response.status == HTTPStatus.OK
    return await response.json()


@pytest.fixture(name="config")
def mock_config() -> dict[str, Any]:
    """Fixture to provide calendar configuration.yaml."""
    return {}


@pytest.fixture(name="setup_platform_cb")
async def mock_setup_platform_cb(
    hass: HomeAssistant, config: dict[str, Any]
) -> Callable[[], Awaitable[None]]:
    """Fixture that returns a function to setup the calendar platform."""

    async def _run() -> None:
        assert await async_setup_component(
            hass, "calendar", {"calendar": {**CALDAV_CONFIG, **config}}
        )
        await hass.async_block_till_done()

    return _run


@pytest.mark.parametrize(
    ("calendar_names", "config", "expected_entities"),
    [
        (["First", "Second"], {}, ["calendar.first", "calendar.second"]),
        (
            ["First", "Second"],
            {"calendars": ["none"]},
            [],
        ),
        (["First", "Second"], {"calendars": ["Second"]}, ["calendar.second"]),
        (
            ["First", "Second"],
            {
                "custom_calendars": {
                    "name": "HomeOffice",
                    "calendar": "Second",
                    "search": "HomeOffice",
                },
            },
            ["calendar.second_homeoffice"],
        ),
    ],
    ids=("config", "no_match", "match", "custom"),
)
async def test_setup_component_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    expected_entities: list[str],
    setup_platform_cb: Callable[[], Awaitable[None]],
) -> None:
    """Test setup component with wrong calendar."""
    await setup_platform_cb()

    all_calendar_entities = hass.states.async_entity_ids("calendar")
    # Entities are added after a concurrent first refresh, so order is not
    # guaranteed; assert on the set of created entities instead.
    assert sorted(all_calendar_entities) == sorted(expected_entities)


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(17, 45))
async def test_ongoing_event(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the ongoing event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(17, 30))
async def test_just_ended_event(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the next ongoing event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(17, 00))
async def test_ongoing_event_different_tz(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the ongoing event with another timezone is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "Enjoy the sun",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 16:30:00",
        "description": "Sunny day",
        "end_time": "2017-11-27 17:30:00",
        "location": "San Francisco",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(19, 10))
async def test_ongoing_floating_event_returned(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that floating events without timezones work."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a floating Event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 19:00:00",
        "end_time": "2017-11-27 20:00:00",
        "location": "Hamburg",
        "description": "What a day",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(8, 30))
async def test_ongoing_event_with_offset(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the offset is taken into account."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is an offset event",
        "all_day": False,
        "offset_reached": True,
        "start_time": "2017-11-27 10:00:00",
        "end_time": "2017-11-27 11:00:00",
        "location": "Hamburg",
        "description": "Surprisingly shiny",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize(
    ("tz", "config"),
    [
        (
            UTC,
            {
                "custom_calendars": [
                    {
                        "name": CALENDAR_NAME,
                        "calendar": CALENDAR_NAME,
                        "search": "This is a normal event",
                    }
                ]
            },
        )
    ],
)
@pytest.mark.freeze_time(_local_datetime(12, 00))
async def test_matching_filter(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the matching event is returned."""
    await setup_platform_cb()

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
        "supported_features": CalendarEntityFeature.CREATE_EVENT,
    }


@pytest.mark.parametrize(
    ("tz", "config"),
    [
        (
            UTC,
            {
                "custom_calendars": [
                    {
                        "name": CALENDAR_NAME,
                        "calendar": CALENDAR_NAME,
                        "search": r".*rainy",
                    }
                ]
            },
        )
    ],
)
@pytest.mark.freeze_time(_local_datetime(12, 00))
async def test_matching_filter_real_regexp(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the event matching the regexp is returned."""

    await setup_platform_cb()

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
        "supported_features": CalendarEntityFeature.CREATE_EVENT,
    }


@pytest.mark.parametrize(
    "config",
    [
        {
            "custom_calendars": [
                {
                    "name": CALENDAR_NAME,
                    "calendar": CALENDAR_NAME,
                    "search": "This is a normal event",
                }
            ]
        }
    ],
)
@pytest.mark.freeze_time(_local_datetime(20, 00))
async def test_filter_matching_past_event(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the matching past event is not returned."""

    await setup_platform_cb()

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == "off"
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "offset_reached": False,
        "supported_features": CalendarEntityFeature.CREATE_EVENT,
    }


@pytest.mark.parametrize(
    "config",
    [
        {
            "custom_calendars": [
                {
                    "name": CALENDAR_NAME,
                    "calendar": CALENDAR_NAME,
                    "search": "This is a non-existing event",
                }
            ]
        }
    ],
)
@pytest.mark.freeze_time(_local_datetime(12, 00))
async def test_no_result_with_filtering(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that nothing is returned since nothing matches."""
    await setup_platform_cb()

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == "off"
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "offset_reached": False,
        "supported_features": CalendarEntityFeature.CREATE_EVENT,
    }


@pytest.mark.parametrize(
    ("tz", "target_datetime"),
    [
        # Early
        (UTC, dt.datetime(2017, 11, 27, 0, 30)),
        (AMERICA_NEW_YORK, dt.datetime(2017, 11, 27, 0, 30)),
        (ASIA_BAGHDAD, dt.datetime(2017, 11, 27, 0, 30)),
        # Mid
        (UTC, dt.datetime(2017, 11, 27, 12, 30)),
        (AMERICA_NEW_YORK, dt.datetime(2017, 11, 27, 12, 30)),
        (ASIA_BAGHDAD, dt.datetime(2017, 11, 27, 12, 30)),
        # Late
        (UTC, dt.datetime(2017, 11, 27, 23, 30)),
        (AMERICA_NEW_YORK, dt.datetime(2017, 11, 27, 23, 30)),
        (ASIA_BAGHDAD, dt.datetime(2017, 11, 27, 23, 30)),
    ],
)
async def test_all_day_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    target_datetime: dt.datetime,
) -> None:
    """Test that the event lasting the whole day is returned.

    Specifically when it's early in the local day.
    """
    freezer.move_to(target_datetime.replace(tzinfo=dt_util.get_default_time_zone()))
    assert await async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                **CALDAV_CONFIG,
                "custom_calendars": [
                    {"name": CALENDAR_NAME, "calendar": CALENDAR_NAME, "search": ".*"}
                ],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is an all day event",
        "all_day": True,
        "offset_reached": False,
        "start_time": "2017-11-27 00:00:00",
        "end_time": "2017-11-28 00:00:00",
        "location": "Hamburg",
        "description": "What a beautiful day",
        "supported_features": CalendarEntityFeature.CREATE_EVENT,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(21, 45))
async def test_event_rrule(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the future recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 22:00:00",
        "end_time": "2017-11-27 22:30:00",
        "location": "Hamburg",
        "description": "Every day for a while",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(22, 15))
async def test_event_rrule_ongoing(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the current recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 22:00:00",
        "end_time": "2017-11-27 22:30:00",
        "location": "Hamburg",
        "description": "Every day for a while",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(22, 45))
async def test_event_rrule_duration(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the future recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a recurring event with a duration",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 23:00:00",
        "end_time": "2017-11-27 23:30:00",
        "location": "Hamburg",
        "description": "Every day for a while as well",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(23, 15))
async def test_event_rrule_duration_ongoing(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the ongoing recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a recurring event with a duration",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 23:00:00",
        "end_time": "2017-11-27 23:30:00",
        "location": "Hamburg",
        "description": "Every day for a while as well",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(23, 37))
async def test_event_rrule_endless(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the endless recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a recurring event that never ends",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 23:45:00",
        "end_time": "2017-11-27 23:59:59",
        "location": "Hamburg",
        "description": "Every day forever",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize(
    ("tz", "target_datetime"),
    [
        # Early
        (UTC, dt.datetime(2016, 12, 1, 0, 30)),
        (AMERICA_NEW_YORK, dt.datetime(2016, 12, 1, 0, 30)),
        (ASIA_BAGHDAD, dt.datetime(2016, 12, 1, 0, 30)),
        # Mid
        (UTC, dt.datetime(2016, 12, 1, 17, 30)),
        (AMERICA_NEW_YORK, dt.datetime(2016, 12, 1, 17, 30)),
        (ASIA_BAGHDAD, dt.datetime(2016, 12, 1, 17, 30)),
        # Late
        (UTC, dt.datetime(2016, 12, 1, 23, 30)),
        (AMERICA_NEW_YORK, dt.datetime(2016, 12, 1, 23, 30)),
        (ASIA_BAGHDAD, dt.datetime(2016, 12, 1, 23, 30)),
    ],
)
async def test_event_rrule_all_day_early(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    target_datetime: dt.datetime,
) -> None:
    """Test recurring all day event is returned early in the day.

    Verifies it's not returned on the first occurrence.
    """
    freezer.move_to(target_datetime.replace(tzinfo=dt_util.get_default_time_zone()))
    assert await async_setup_component(
        hass,
        "calendar",
        {
            "calendar": {
                **CALDAV_CONFIG,
                "custom_calendars": {
                    "name": CALENDAR_NAME,
                    "calendar": CALENDAR_NAME,
                    "search": ".*",
                },
            },
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is a recurring all day event",
        "all_day": True,
        "offset_reached": False,
        "start_time": "2016-12-01 00:00:00",
        "end_time": "2016-12-02 00:00:00",
        "location": "Hamburg",
        "description": "Groundhog Day",
        "supported_features": CalendarEntityFeature.CREATE_EVENT,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(dt_util.as_local(dt.datetime(2015, 11, 27, 0, 15)))
async def test_event_rrule_hourly_on_first(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the endless recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is an hourly recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2015-11-27 00:00:00",
        "end_time": "2015-11-27 00:30:00",
        "location": "Hamburg",
        "description": "The bell tolls for thee",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize("tz", ["UTC"])
@pytest.mark.freeze_time(dt_util.as_local(dt.datetime(2015, 11, 27, 11, 15)))
async def test_event_rrule_hourly_on_last(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that the endless recurring event is returned."""
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is an hourly recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2015-11-27 11:00:00",
        "end_time": "2015-11-27 11:30:00",
        "location": "Hamburg",
        "description": "The bell tolls for thee",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize(
    ("target_datetime"),
    [
        dt.datetime(2015, 11, 27, 0, 45),
        dt.datetime(2015, 11, 27, 11, 45),
        dt.datetime(2015, 11, 27, 12, 15),
    ],
)
async def test_event_rrule_hourly(
    hass: HomeAssistant,
    setup_platform_cb: Callable[[], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
    target_datetime: dt.datetime,
) -> None:
    """Test that the endless recurring event is returned."""
    freezer.move_to(dt_util.as_local(target_datetime))
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_OFF


async def test_get_events(
    hass: HomeAssistant,
    get_api_events: Callable[[str], Awaitable[dict[str, Any]]],
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
) -> None:
    """Test that all events are returned on API."""
    await setup_platform_cb()

    events = await get_api_events(TEST_ENTITY)
    assert len(events) == 18
    assert calendars[0].call


@pytest.mark.parametrize(
    "config",
    [
        {
            "custom_calendars": [
                {
                    "name": CALENDAR_NAME,
                    "calendar": CALENDAR_NAME,
                    "search": "This is a normal event",
                }
            ]
        }
    ],
)
async def test_get_events_custom_calendars(
    hass: HomeAssistant,
    get_api_events: Callable[[str], Awaitable[dict[str, Any]]],
    setup_platform_cb: Callable[[], Awaitable[None]],
) -> None:
    """Test that only searched events are returned on API."""
    await setup_platform_cb()

    events = await get_api_events("calendar.example_example")
    assert events == [
        {
            "end": {"dateTime": "2017-11-27T10:00:00-08:00"},
            "start": {"dateTime": "2017-11-27T09:00:00-08:00"},
            "summary": "This is a normal event",
            "location": "Hamburg",
            "description": "Surprisingly rainy",
            "uid": "0",
            "recurrence_id": None,
            "rrule": None,
            "status": None,
        }
    ]


async def test_get_events_with_recurrence_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that uid and recurrence_id are populated from VEVENT data."""
    vevent_with_recurrence_id = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:original-event-uid
RECURRENCE-ID:20171127T170000Z
DTSTAMP:20171125T000000Z
DTSTART:20171127T180000Z
DTEND:20171127T190000Z
SUMMARY:Modified occurrence
LOCATION:Hamburg
DESCRIPTION:This occurrence was moved
END:VEVENT
END:VCALENDAR"""
    events = await _get_api_events_for_vevent(
        hass, hass_client, vevent_with_recurrence_id, "original-event-uid"
    )

    assert len(events) == 1
    assert events[0]["uid"] == "original-event-uid"
    assert events[0]["recurrence_id"] == "2017-11-27 17:00:00+00:00"
    assert events[0]["summary"] == "Modified occurrence"


ICS_WITH_STATUS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:status-event-uid
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
SUMMARY:This is an event with a status
LOCATION:Hamburg
DESCRIPTION:Surprisingly rainy
STATUS:{status}
END:VEVENT
END:VCALENDAR"""


@pytest.mark.parametrize(
    ("status", "expected_status"),
    [
        pytest.param("TENTATIVE", "tentative", id="tentative"),
        pytest.param("CONFIRMED", "confirmed", id="confirmed"),
        pytest.param("Tentative", "tentative", id="mixed_case"),
        pytest.param("X-VENDOR-SPECIFIC", None, id="unsupported_value"),
    ],
)
async def test_get_events_with_status(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    status: str,
    expected_status: str | None,
) -> None:
    """Test that the rfc5545 STATUS property is populated from VEVENT data."""
    events = await _get_api_events_for_vevent(
        hass, hass_client, ICS_WITH_STATUS.format(status=status), "status-event-uid"
    )

    assert len(events) == 1
    assert events[0]["status"] == expected_status


def _mock_calendar_holding(name: str, vevents: list[str]) -> Mock:
    """Return a mock calendar holding exactly the given VEVENTs."""
    calendar = _mock_calendar(name)
    calendar.search = MagicMock(
        return_value=[
            Event(None, f"{idx}.ics", vevent, calendar, str(idx))
            for idx, vevent in enumerate(vevents)
        ]
    )
    return calendar


async def test_cancelled_event_is_not_returned(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that an event called off is not returned by the API."""
    events = await _get_api_events_for_vevent(
        hass,
        hass_client,
        ICS_WITH_STATUS.format(status="CANCELLED"),
        "status-event-uid",
    )

    assert events == []


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.parametrize(
    ("calendars"),
    [[_mock_calendar_holding("Example", [ICS_WITH_STATUS.format(status="CANCELLED")])]],
)
@pytest.mark.freeze_time(_local_datetime(17, 30))
async def test_cancelled_event_is_not_the_ongoing_event(
    hass: HomeAssistant, setup_platform_cb: Callable[[], Awaitable[None]]
) -> None:
    """Test that an event called off does not turn the entity on.

    The event would be ongoing at this time were it not cancelled, so this
    covers the state path rather than the API one.
    """
    await setup_platform_cb()

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("calendars"),
    [
        [
            _mock_calendar("Calendar 1", supported_components=["VEVENT"]),
            _mock_calendar("Calendar 2", supported_components=["VEVENT", "VJOURNAL"]),
            _mock_calendar("Calendar 3", supported_components=["VTODO"]),
            _mock_calendar("Calendar 4", supported_components=[]),
        ]
    ],
)
async def test_calendar_components(hass: HomeAssistant) -> None:
    """Test that only calendars that support events are created."""

    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.calendar_1")
    assert state

    state = hass.states.get("calendar.calendar_2")
    assert state

    # No entity created for To-do only component
    state = hass.states.get("calendar.calendar_3")
    assert not state

    # No entity created when no components exist
    state = hass.states.get("calendar.calendar_4")
    assert not state


async def test_calendar_name_resolved_in_executor(
    hass: HomeAssistant, calendars: list[Mock]
) -> None:
    """Test the calendar display name is resolved outside the event loop."""

    def _get_display_name() -> str:
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return CALENDAR_NAME

    calendars[0].get_display_name.side_effect = _get_display_name
    client = MagicMock()
    client.get_principal().get_calendars.return_value = calendars

    assert await async_get_calendars(hass, client, "VEVENT") == [
        (calendars[0], CALENDAR_NAME)
    ]


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(_local_datetime(17, 30))
async def test_setup_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a calendar entity from a config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.name == CALENDAR_NAME
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": CALENDAR_NAME,
        "message": "This is an all day event",
        "all_day": True,
        "start_time": "2017-11-27 00:00:00",
        "end_time": "2017-11-28 00:00:00",
        "location": "Hamburg",
        "description": "What a beautiful day",
        "supported_features": SUPPORTED_FEATURES,
    }


@pytest.mark.parametrize(
    ("calendars"),
    [
        [
            _mock_calendar("Calendar 1", supported_components=["VEVENT"]),
            _mock_calendar("Calendar 2", supported_components=["VEVENT", "VJOURNAL"]),
            _mock_calendar("Calendar 3", supported_components=["VTODO"]),
            _mock_calendar("Calendar 4", supported_components=[]),
        ]
    ],
)
async def test_config_entry_supported_components(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test calendars are only created for VEVENT types.

    This applies when using a config entry.
    """
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get("calendar.calendar_1")
    assert state

    state = hass.states.get("calendar.calendar_2")
    assert state

    # No entity created for To-do only component
    state = hass.states.get("calendar.calendar_3")
    assert not state

    # No entity created when no components exist
    state = hass.states.get("calendar.calendar_4")
    assert not state


@pytest.mark.parametrize(
    ("calendars", "expected_colors"),
    [
        pytest.param(
            [_mock_calendar(CALENDAR_NAME, color="#FF0000")],
            {TEST_ENTITY: "#FF0000"},
            id="rgb",
        ),
        pytest.param(
            [_mock_calendar(CALENDAR_NAME, color="#1BADF8FF")],
            {TEST_ENTITY: "#1BADF8"},
            id="alpha",
        ),
        pytest.param(
            [_mock_calendar(CALENDAR_NAME, color="red")],
            {TEST_ENTITY: None},
            id="not_hex",
        ),
        pytest.param(
            [_mock_calendar(CALENDAR_NAME)],
            {TEST_ENTITY: None},
            id="no_color",
        ),
        pytest.param(
            [_mock_calendar(CALENDAR_NAME, color=DAVError())],
            {TEST_ENTITY: None},
            id="dav_error",
        ),
        pytest.param(
            [
                _mock_calendar(
                    CALENDAR_NAME, color=caldav_requests.exceptions.ConnectionError()
                )
            ],
            {TEST_ENTITY: None},
            id="connection_error",
        ),
        pytest.param(
            [_mock_calendar(CALENDAR_NAME, color=caldav_requests.exceptions.Timeout())],
            {TEST_ENTITY: None},
            id="timeout",
        ),
        pytest.param(
            [
                _mock_calendar(
                    CALENDAR_NAME,
                    color=caldav_requests.exceptions.ChunkedEncodingError(),
                )
            ],
            {TEST_ENTITY: None},
            id="chunked_encoding_error",
        ),
        pytest.param(
            [
                _mock_calendar("First", color="#FF0000"),
                _mock_calendar("Second", color="#0000FF"),
            ],
            {"calendar.first": "#FF0000", "calendar.second": "#0000FF"},
            id="several",
        ),
    ],
)
async def test_config_entry_initial_color(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    expected_colors: dict[str, str | None],
) -> None:
    """Test a new calendar entity takes the color its calendar has, if it can."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    for entity_id, expected_color in expected_colors.items():
        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.options.get(CALENDAR_DOMAIN, {}).get("color") == expected_color


@pytest.mark.parametrize(
    "calendars",
    [
        [
            _mock_calendar("Existing", color="#FF0000"),
            _mock_calendar("New", color="#0000FF"),
        ]
    ],
)
async def test_config_entry_initial_color_existing_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    calendars: list[Mock],
) -> None:
    """Test the color is only read for a calendar that has no entity yet."""
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        Platform.CALENDAR,
        DOMAIN,
        f"{config_entry.entry_id}-{calendars[0].id}",
        config_entry=config_entry,
        suggested_object_id="existing",
    )
    await hass.config_entries.async_setup(config_entry.entry_id)

    calendars[0].get_property.assert_not_called()
    entity = entity_registry.async_get("calendar.new")
    assert entity
    assert entity.options.get(CALENDAR_DOMAIN, {}).get("color") == "#0000FF"


async def test_yaml_calendar_skips_color(
    hass: HomeAssistant,
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
) -> None:
    """Test a calendar set up from YAML doesn't read the color, having no unique id."""
    await setup_platform_cb()

    assert hass.states.get(TEST_ENTITY)
    calendars[0].get_property.assert_not_called()


def _ics_event(uid: str, dates: str) -> str:
    """Return a VCALENDAR holding a single VEVENT with the given dates."""
    return (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//CalDAV Client//EN\n"
        f"BEGIN:VEVENT\nUID:{uid}\nDTSTAMP:20240801T000000Z\n{dates}\n"
        f"SUMMARY:{uid}\nEND:VEVENT\nEND:VCALENDAR\n"
    )


@pytest.mark.parametrize("tz", [AMERICA_NEW_YORK])
@pytest.mark.parametrize(
    "calendars",
    [
        [
            _mock_calendar_holding(
                CALENDAR_NAME,
                [
                    _ics_event(
                        "late", "DTSTART:20240829T150000Z\nDTEND:20240829T160000Z"
                    ),
                    _ics_event(
                        "all-day",
                        "DTSTART;VALUE=DATE:20240829\nDTEND;VALUE=DATE:20240830",
                    ),
                    _ics_event(
                        "early", "DTSTART:20240829T120000Z\nDTEND:20240829T130000Z"
                    ),
                ],
            )
        ]
    ],
)
async def test_get_events_sorted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_platform_cb: Callable[[], Awaitable[None]],
) -> None:
    """Test events are returned in order, including all-day events."""
    await setup_platform_cb()

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{TEST_ENTITY}"
        "?start=2024-08-29T00:00:00-04:00&end=2024-08-30T00:00:00-04:00"
    )
    assert response.status == HTTPStatus.OK
    assert [event["summary"] for event in await response.json()] == [
        "all-day",
        "early",
        "late",
    ]


@pytest.mark.parametrize("tz", [AMERICA_NEW_YORK])
@pytest.mark.parametrize(
    "calendars",
    [
        [
            _mock_calendar_holding(
                CALENDAR_NAME,
                [
                    # 01:15 EST, after the clocks fell back
                    _ics_event(
                        "second", "DTSTART:20241103T061500Z\nDTEND:20241103T063000Z"
                    ),
                    # 01:30 EDT, before the clocks fell back
                    _ics_event(
                        "first", "DTSTART:20241103T053000Z\nDTEND:20241103T054500Z"
                    ),
                ],
            )
        ]
    ],
)
async def test_get_events_sorted_dst_fallback(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_platform_cb: Callable[[], Awaitable[None]],
) -> None:
    """Test events in the repeated hour are returned in chronological order."""
    await setup_platform_cb()

    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{TEST_ENTITY}"
        "?start=2024-11-03T00:00:00-04:00&end=2024-11-04T00:00:00-05:00"
    )
    assert response.status == HTTPStatus.OK
    assert [event["summary"] for event in await response.json()] == [
        "first",
        "second",
    ]


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.parametrize(
    ("service_data", "expected_ics_fields"),
    [
        # Basic event with all fields
        (
            {
                "summary": "Test Event",
                "start_date_time": "2025-08-06T10:00:00+00:00",
                "end_date_time": "2025-08-06T11:00:00+00:00",
                "description": "Test Description",
                "location": "Test Location",
            },
            {
                "description": "Test Description",
                "dtend": dt.datetime(
                    2025, 8, 6, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "dtstart": dt.datetime(
                    2025, 8, 6, 10, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "location": "Test Location",
                "summary": "Test Event",
            },
        ),
        # Event with only required fields
        (
            {
                "summary": "Required Only",
                "start_date_time": "2025-08-07T09:00:00+00:00",
                "end_date_time": "2025-08-07T10:00:00+00:00",
            },
            {
                "summary": "Required Only",
                "dtstart": dt.datetime(
                    2025, 8, 7, 9, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "dtend": dt.datetime(
                    2025, 8, 7, 10, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
            },
        ),
        # All-day event (date only)
        (
            {
                "summary": "All Day Event",
                "start_date": "2025-08-08",
                "end_date": "2025-08-09",
            },
            {
                "summary": "All Day Event",
                "dtstart": dt.date(2025, 8, 8),
                "dtend": dt.date(2025, 8, 9),
            },
        ),
        # Event with different timezone
        (
            {
                "summary": "Different TZ",
                "start_date_time": "2025-08-07T09:00:00+02:00",
                "end_date_time": "2025-08-07T10:00:00+02:00",
            },
            {
                "summary": "Different TZ",
                "dtstart": dt.datetime(
                    2025, 8, 7, 7, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "dtend": dt.datetime(
                    2025, 8, 7, 8, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
            },
        ),
        # Rrule is not supported in API (async_call) calls.
    ],
)
async def test_add_vevent(
    hass: HomeAssistant,
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    service_data: dict,
    expected_ics_fields: dict,
) -> None:
    """Test adding a VEVENT to the calendar."""
    await setup_platform_cb()

    calendars[0].add_event = MagicMock(return_value=[])
    await hass.services.async_call(
        "calendar",
        "create_event",
        service_data,
        target={"entity_id": TEST_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    calendars[0].add_event.assert_called_once()
    assert calendars[0].add_event.call_args
    assert calendars[0].add_event.call_args[1] == expected_ics_fields


SINGLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VEVENT
UID:single
DTSTAMP:20261101T000000Z
DTSTART:20261110T150000Z
DTEND:20261110T160000Z
SUMMARY:Dentist
DESCRIPTION:Bring the card
LOCATION:Main street
END:VEVENT
END:VCALENDAR
"""

SERIES_MAIN = """BEGIN:VEVENT
UID:series
DTSTAMP:20261001T000000Z
DTSTART;TZID=America/New_York:20261026T090000
DTEND;TZID=America/New_York:20261026T093000
RRULE:FREQ=WEEKLY;COUNT=8
SUMMARY:Weekly
DESCRIPTION:Team sync
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT15M
DESCRIPTION:Reminder
END:VALARM
END:VEVENT
"""
SERIES_OVERRIDE = """BEGIN:VEVENT
UID:series
DTSTAMP:20261001T000000Z
RECURRENCE-ID;TZID=America/New_York:20261116T090000
DTSTART;TZID=America/New_York:20261116T100000
DTEND;TZID=America/New_York:20261116T103000
SUMMARY:Weekly moved
END:VEVENT
"""
# Weekly from before the end of daylight saving time, with one occurrence moved
SERIES_ICS = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
{SERIES_MAIN}{SERIES_OVERRIDE}END:VCALENDAR
"""
SERIES_OVERRIDE_FIRST_ICS = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
{SERIES_OVERRIDE}{SERIES_MAIN}END:VCALENDAR
"""

NEW_YORK_SERIES_ICS = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
{SERIES_MAIN}END:VCALENDAR
"""

MONDAYS_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VEVENT
UID:mondays
DTSTAMP:20261101T000000Z
DTSTART;TZID=America/New_York:20261102T090000
DTEND;TZID=America/New_York:20261102T093000
RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=4
SUMMARY:Planning
END:VEVENT
END:VCALENDAR
"""

FLOATING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VEVENT
UID:floating
DTSTAMP:20261101T000000Z
DTSTART:20261110T070000
DTEND:20261110T073000
SUMMARY:Run
END:VEVENT
END:VCALENDAR
"""

# SERIES_ICS with its first occurrence moved from 09:00 to 11:00
FIRST_MOVED_ICS = SERIES_ICS.replace(
    "RECURRENCE-ID;TZID=America/New_York:20261116T090000\n"
    "DTSTART;TZID=America/New_York:20261116T100000\n"
    "DTEND;TZID=America/New_York:20261116T103000",
    "RECURRENCE-ID;TZID=America/New_York:20261026T090000\n"
    "DTSTART;TZID=America/New_York:20261026T110000\n"
    "DTEND;TZID=America/New_York:20261026T113000",
)

# NEW_YORK_SERIES_ICS with its first occurrence deleted
FIRST_DELETED_ICS = NEW_YORK_SERIES_ICS.replace(
    "RRULE:FREQ=WEEKLY;COUNT=8",
    "RRULE:FREQ=WEEKLY;COUNT=8\nEXDATE;TZID=America/New_York:20261026T090000",
)

WINDOWS_TIME_ZONE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VTIMEZONE
TZID:Eastern Standard Time
BEGIN:STANDARD
DTSTART:16010101T020000
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010101T020000
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:windows
DTSTAMP:20261101T000000Z
DTSTART;TZID=Eastern Standard Time:20261110T090000
DTEND;TZID=Eastern Standard Time:20261110T100000
SUMMARY:Review
END:VEVENT
END:VCALENDAR
"""

# SERIES_ICS with its first occurrence cancelled
FIRST_CANCELLED_ICS = FIRST_MOVED_ICS.replace(
    "SUMMARY:Weekly moved", "SUMMARY:Weekly moved\nSTATUS:CANCELLED"
)

# BYSETPOS has to be between 1 and 366, or -366 and -1
BROKEN_RULE = "RRULE:FREQ=WEEKLY;COUNT=8;BYSETPOS=0"

# Starting at the first 01:30 of the night daylight saving time ends
REPEATED_HOUR_SERIES_ICS = NEW_YORK_SERIES_ICS.replace(
    "20261026T090000", "20261101T013000"
).replace("20261026T093000", "20261101T014500")

# Two weeks from before daylight saving time ends
UNTIL_BEFORE_DST_END_ICS = (
    NEW_YORK_SERIES_ICS.replace("20261026T090000", "20261019T090000")
    .replace("20261026T093000", "20261019T093000")
    .replace("FREQ=WEEKLY;COUNT=8", "FREQ=WEEKLY;UNTIL=20261026T130000Z")
)

# SERIES_ICS ending on a date instead of after a number of occurrences
SERIES_UNTIL_ICS = SERIES_ICS.replace(
    "RRULE:FREQ=WEEKLY;COUNT=8", "RRULE:FREQ=WEEKLY;UNTIL=20261214T140000Z"
)

ALL_DAY_SERIES_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VEVENT
UID:all-day-series
DTSTAMP:20261101T000000Z
DTSTART;VALUE=DATE:20261120
DURATION:P1D
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:Holiday
END:VEVENT
END:VCALENDAR
"""

# An all-day event lasting an hour, which RFC 5545 doesn't allow
ALL_DAY_HOUR_ICS = ALL_DAY_SERIES_ICS.replace(
    "DURATION:P1D\nRRULE:FREQ=DAILY;COUNT=5", "DURATION:PT1H"
)

# An invitation to one occurrence of a series that is held by someone else
INVITATION_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//CalDAV Client//EN
BEGIN:VEVENT
UID:invitation
DTSTAMP:20261101T000000Z
RECURRENCE-ID:20261102T150000Z
DTSTART:20261102T150000Z
DTEND:20261102T160000Z
SUMMARY:Review
END:VEVENT
END:VCALENDAR
"""

# Recurrence ids as the integration returns them for occurrences of SERIES_ICS
FIRST_OCCURRENCE = "2026-10-26 09:00:00-04:00"
SECOND_OCCURRENCE = "2026-11-02 09:00:00-05:00"


@pytest.fixture(name="stored_event")
def mock_stored_event(calendars: list[Mock], ics: str) -> Event:
    """Fixture to return a CalDAV object the calendar finds by UID."""
    client = MagicMock()
    client.url = URL("http://test.local/")
    client.put.return_value.status = 204
    client.delete.return_value.status = 204
    stored_event = Event(client, "event.ics", ics, calendars[0])
    calendars[0].get_event_by_uid = MagicMock(return_value=stored_event)
    return stored_event


@pytest.fixture(name="setup_config_entry")
async def mock_setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Fixture to set up the calendar from a config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)


async def _ws_call(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, **msg: Any
) -> dict[str, Any]:
    """Send a websocket command for the test entity and return the response."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"entity_id": TEST_ENTITY, **msg})
    return await client.receive_json()


@pytest.mark.parametrize("tz", [AMERICA_NEW_YORK])
@pytest.mark.parametrize(
    ("ics", "uid", "recurrence_id", "event"),
    [
        pytest.param(
            SINGLE_ICS,
            "single",
            "",
            {
                "summary": "Dentist moved",
                "dtstart": "2026-11-11T09:00:00",
                "dtend": "2026-11-11T10:00:00",
                "description": "",
                "location": "Second street",
            },
            id="single",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS,
            "all-day-series",
            "",
            {"summary": "Long holiday", "dtstart": "2026-11-20", "dtend": "2026-11-22"},
            id="series_keeps_rrule",
        ),
        pytest.param(
            NEW_YORK_SERIES_ICS,
            "series",
            FIRST_OCCURRENCE,
            {
                "summary": "Daily",
                "dtstart": "2026-10-26T08:00:00",
                "dtend": "2026-10-26T08:30:00",
                "rrule": "FREQ=DAILY;COUNT=3",
            },
            id="series_from_first_occurrence",
        ),
        pytest.param(
            SERIES_OVERRIDE_FIRST_ICS,
            "series",
            FIRST_OCCURRENCE,
            {
                "summary": "Weekly renamed",
                "dtstart": "2026-10-26T09:00:00",
                "dtend": "2026-10-26T09:30:00",
            },
            id="override_listed_first",
        ),
        pytest.param(
            SERIES_ICS,
            "series",
            FIRST_OCCURRENCE,
            {
                "summary": "Weekly renamed",
                "dtstart": "2026-10-26T09:00:00",
                "dtend": "2026-10-26T10:00:00",
                "rrule": "FREQ=WEEKLY;COUNT=8",
            },
            id="same_start_and_rrule_with_override",
        ),
        pytest.param(
            MONDAYS_ICS,
            "mondays",
            "",
            {
                "summary": "Planning",
                "dtstart": "2026-11-02T10:00:00",
                "dtend": "2026-11-02T10:30:00",
            },
            id="pinned_days_new_time",
        ),
        pytest.param(
            MONDAYS_ICS,
            "mondays",
            "",
            {
                "summary": "Planning",
                "dtstart": "2026-11-09T09:00:00",
                "dtend": "2026-11-09T09:30:00",
            },
            id="pinned_days_next_week",
        ),
        pytest.param(
            MONDAYS_ICS,
            "mondays",
            "",
            {
                "summary": "Planning",
                "dtstart": "2026-11-03T09:00:00",
                "dtend": "2026-11-03T09:30:00",
                "rrule": "FREQ=WEEKLY;BYDAY=TU;COUNT=4",
            },
            id="pinned_days_new_day_and_rrule",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS.replace("FREQ=DAILY", "FREQ=MONTHLY;BYMONTHDAY=20"),
            "all-day-series",
            "",
            {"summary": "Rent", "dtstart": "2026-11-20", "dtend": "2026-11-21"},
            id="pinned_days_all_day_same_day",
        ),
        pytest.param(
            NEW_YORK_SERIES_ICS,
            "series",
            "",
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T09:00:00",
                "dtend": "2026-10-26T09:30:00",
                "rrule": "FREQ=WEEKLY;UNTIL=20261116T090000",
            },
            id="until_utc_for_time_zone",
        ),
        pytest.param(
            FLOATING_ICS,
            "floating",
            "",
            {
                "summary": "Run",
                "dtstart": "2026-11-10T07:00:00",
                "dtend": "2026-11-10T07:30:00",
                "rrule": "FREQ=DAILY;UNTIL=20261201T155959Z",
            },
            id="until_floating",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS,
            "all-day-series",
            "",
            {
                "summary": "Holiday",
                "dtstart": "2026-11-20",
                "dtend": "2026-11-21",
                "rrule": "FREQ=DAILY;UNTIL=20261124T050000Z",
            },
            id="until_date_for_all_day",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS,
            "all-day-series",
            "",
            {
                "summary": "Holiday",
                "dtstart": "2026-11-20",
                "dtend": "2026-11-21",
                "rrule": "FREQ=DAILY;UNTIL=20261124",
            },
            id="until_date_kept_for_all_day",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS.replace("RRULE:FREQ=DAILY;COUNT=5\n", ""),
            "all-day-series",
            "",
            {
                "summary": "Holiday",
                "dtstart": "2026-11-20T09:00:00",
                "dtend": "2026-11-20T10:00:00",
            },
            id="all_day_to_timed",
        ),
        pytest.param(
            SERIES_UNTIL_ICS,
            "series",
            FIRST_OCCURRENCE,
            {
                "summary": "Weekly renamed",
                "dtstart": "2026-10-26T09:00:00",
                "dtend": "2026-10-26T09:30:00",
                "rrule": "FREQ=WEEKLY;UNTIL=20261214T090000",
            },
            id="same_until_with_override",
        ),
        pytest.param(
            MONDAYS_ICS.replace("COUNT=4", "UNTIL=20261123T090000"),
            "mondays",
            "",
            {
                "summary": "Planning",
                "dtstart": "2026-11-09T10:00:00",
                "dtend": "2026-11-09T10:30:00",
            },
            id="stored_until_without_time_zone",
        ),
        pytest.param(
            WINDOWS_TIME_ZONE_ICS,
            "windows",
            "",
            {
                "summary": "Review",
                "dtstart": "2026-11-10T10:00:00",
                "dtend": "2026-11-10T11:00:00",
            },
            id="windows_time_zone_name",
        ),
        pytest.param(
            FLOATING_ICS,
            "floating",
            "",
            {
                "summary": "Run",
                "dtstart": "2026-03-08T02:30:00",
                "dtend": "2026-03-08T03:00:00",
            },
            id="floating_in_skipped_hour",
        ),
        pytest.param(
            SERIES_UNTIL_ICS.replace(SERIES_OVERRIDE, ""),
            "series",
            FIRST_OCCURRENCE,
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T10:00:00",
                "dtend": "2026-10-26T10:30:00",
            },
            id="until_moves_with_start",
        ),
        pytest.param(
            UNTIL_BEFORE_DST_END_ICS,
            "series",
            "",
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T09:00:00",
                "dtend": "2026-10-26T09:30:00",
            },
            id="until_moves_across_daylight_saving_time",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS.replace("COUNT=5", "UNTIL=20261124"),
            "all-day-series",
            "",
            {"summary": "Holiday", "dtstart": "2026-11-21", "dtend": "2026-11-22"},
            id="until_moves_with_all_day_start",
        ),
        pytest.param(
            FLOATING_ICS.replace(
                "SUMMARY:Run", "RRULE:FREQ=DAILY;UNTIL=20261112T070000\nSUMMARY:Run"
            ),
            "floating",
            "",
            {
                "summary": "Run",
                "dtstart": "2026-11-10T08:00:00",
                "dtend": "2026-11-10T08:30:00",
            },
            id="until_moves_with_floating_start",
        ),
        pytest.param(
            ALL_DAY_HOUR_ICS,
            "all-day-series",
            "",
            {"summary": "Holiday", "dtstart": "2026-11-20", "dtend": "2026-11-21"},
            id="all_day_lasting_an_hour",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    calendars: list[Mock],
    stored_event: Event,
    snapshot: SnapshotAssertion,
    uid: str,
    recurrence_id: str,
    event: dict[str, Any],
) -> None:
    """Test updating an event or a whole series."""
    response = await _ws_call(
        hass,
        hass_ws_client,
        type="calendar/event/update",
        uid=uid,
        recurrence_id=recurrence_id,
        recurrence_range="THISANDFUTURE",
        event=event,
    )

    assert response["success"]
    calendars[0].get_event_by_uid.assert_called_once_with(uid)
    assert stored_event.client.put.call_args.args[1] == snapshot


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.parametrize(
    ("ics", "uid", "event"),
    [
        pytest.param(
            NEW_YORK_SERIES_ICS,
            "series",
            # 09:00 in New York before daylight saving time ends, sent in UTC
            {
                "summary": "Weekly renamed",
                "dtstart": "2026-10-26T13:00:00",
                "dtend": "2026-10-26T13:30:00",
            },
            id="series_title_only",
        ),
        pytest.param(
            NEW_YORK_SERIES_ICS,
            "series",
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T14:00:00",
                "dtend": "2026-10-26T15:00:00",
            },
            id="series_new_time",
        ),
        pytest.param(
            NEW_YORK_SERIES_ICS,
            "series",
            # 01:30 to 01:45 EDT, the first time of the hour that repeats
            {
                "summary": "Weekly",
                "dtstart": "2026-11-01T05:30:00",
                "dtend": "2026-11-01T05:45:00",
            },
            id="series_first_of_repeated_hour",
        ),
        pytest.param(
            FLOATING_ICS,
            "floating",
            {
                "summary": "Run",
                "dtstart": "2026-11-10T08:00:00",
                "dtend": "2026-11-10T08:30:00",
            },
            id="floating",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_event_keeps_time_zone(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    snapshot: SnapshotAssertion,
    uid: str,
    event: dict[str, Any],
) -> None:
    """Test an update keeps the time zone of the event, or its floating time."""
    response = await _ws_call(
        hass, hass_ws_client, type="calendar/event/update", uid=uid, event=event
    )

    assert response["success"]
    assert stored_event.client.put.call_args.args[1] == snapshot


@pytest.mark.parametrize(
    ("tz", "ics", "uid", "event"),
    [
        pytest.param(
            UTC,
            NEW_YORK_SERIES_ICS,
            "series",
            # 01:30 EDT to 01:00 EST in New York, a TZID can only mean the first
            {
                "summary": "Weekly",
                "dtstart": "2026-11-01T05:30:00",
                "dtend": "2026-11-01T06:00:00",
            },
            id="second_of_repeated_hour",
        ),
        pytest.param(
            AMERICA_NEW_YORK,
            SINGLE_ICS,
            "single",
            # 02:30 doesn't exist in New York on that day
            {
                "summary": "Dentist",
                "dtstart": "2026-03-08T02:30:00",
                "dtend": "2026-03-08T03:00:00",
            },
            id="skipped_hour",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_event_daylight_saving_time(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    uid: str,
    event: dict[str, Any],
) -> None:
    """Test a time skipped or repeated by daylight saving time is refused."""
    response = await _ws_call(
        hass, hass_ws_client, type="calendar/event/update", uid=uid, event=event
    )

    assert response["error"] == {
        "code": "failed",
        "message": (
            "The time is skipped or happens twice because of a daylight saving "
            "time change"
        ),
    }
    stored_event.client.put.assert_not_called()


@pytest.mark.parametrize(
    ("ics", "uid", "recurrence_id"),
    [
        pytest.param(SINGLE_ICS, "single", "", id="single"),
        pytest.param(SERIES_ICS, "series", FIRST_OCCURRENCE, id="series"),
        pytest.param(
            ALL_DAY_HOUR_ICS, "all-day-series", "", id="all_day_lasting_an_hour"
        ),
        pytest.param(
            REPEATED_HOUR_SERIES_ICS,
            "series",
            "2026-11-01 01:30:00-04:00",
            id="series_in_repeated_hour",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_delete_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    calendars: list[Mock],
    stored_event: Event,
    uid: str,
    recurrence_id: str,
) -> None:
    """Test deleting an event or a whole series."""
    response = await _ws_call(
        hass,
        hass_ws_client,
        type="calendar/event/delete",
        uid=uid,
        recurrence_id=recurrence_id,
        recurrence_range="THISANDFUTURE",
    )

    assert response["success"]
    calendars[0].get_event_by_uid.assert_called_once_with(uid)
    stored_event.client.delete.assert_called_once_with(str(stored_event.url))
    stored_event.client.put.assert_not_called()


UPDATE = {
    "type": "calendar/event/update",
    "event": {
        "summary": "Changed",
        "dtstart": "2026-11-02T10:00:00",
        "dtend": "2026-11-02T10:30:00",
    },
}
DELETE = {"type": "calendar/event/delete"}


@pytest.mark.parametrize("msg", [UPDATE, DELETE], ids=["update", "delete"])
@pytest.mark.parametrize(
    ("ics", "uid", "recurrence_id", "recurrence_range"),
    [
        pytest.param(SERIES_ICS, "series", SECOND_OCCURRENCE, "", id="occurrence"),
        pytest.param(
            SERIES_ICS,
            "series",
            SECOND_OCCURRENCE,
            "THISANDFUTURE",
            id="this_and_future",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS, "all-day-series", "2026-11-20", "", id="all_day"
        ),
        pytest.param(
            INVITATION_ICS,
            "invitation",
            "2026-11-02 15:00:00+00:00",
            "THISANDFUTURE",
            id="invitation",
        ),
        pytest.param(
            FIRST_DELETED_ICS,
            "series",
            SECOND_OCCURRENCE,
            "THISANDFUTURE",
            id="first_occurrence_deleted",
        ),
        pytest.param(
            FIRST_CANCELLED_ICS,
            "series",
            SECOND_OCCURRENCE,
            "THISANDFUTURE",
            id="first_occurrence_cancelled",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_occurrence_not_supported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    msg: dict[str, Any],
    uid: str,
    recurrence_id: str,
    recurrence_range: str,
) -> None:
    """Test single occurrences of a recurring event cannot be changed yet."""
    response = await _ws_call(
        hass,
        hass_ws_client,
        uid=uid,
        recurrence_id=recurrence_id,
        recurrence_range=recurrence_range,
        **msg,
    )

    assert not response["success"]
    assert response["error"] == {
        "code": "failed",
        "message": (
            "A recurring event can only be changed or deleted as a whole, "
            "from its first occurrence"
        ),
    }
    stored_event.client.put.assert_not_called()
    stored_event.client.delete.assert_not_called()


@pytest.mark.parametrize(
    ("ics", "uid", "recurrence_id", "event"),
    [
        pytest.param(
            SERIES_ICS,
            "series",
            FIRST_OCCURRENCE,
            {"summary": "Weekly", "dtstart": "2026-10-26", "dtend": "2026-10-27"},
            id="timed_to_all_day",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS,
            "all-day-series",
            "",
            {
                "summary": "Holiday",
                "dtstart": "2026-11-20T09:00:00",
                "dtend": "2026-11-20T10:00:00",
            },
            id="all_day_to_timed",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_series_all_day_change(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    uid: str,
    recurrence_id: str,
    event: dict[str, Any],
) -> None:
    """Test a recurring event can't switch between all-day and timed."""
    response = await _ws_call(
        hass,
        hass_ws_client,
        type="calendar/event/update",
        uid=uid,
        recurrence_id=recurrence_id,
        recurrence_range="THISANDFUTURE",
        event=event,
    )

    assert response["error"] == {
        "code": "failed",
        "message": "A recurring event can't be changed between all-day and timed",
    }
    stored_event.client.put.assert_not_called()


@pytest.mark.parametrize(
    ("ics", "uid", "event"),
    [
        pytest.param(
            SERIES_ICS,
            "series",
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T10:00:00",
                "dtend": "2026-10-26T10:30:00",
            },
            id="override_new_start",
        ),
        pytest.param(
            SERIES_ICS,
            "series",
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T09:00:00",
                "dtend": "2026-10-26T09:30:00",
                "rrule": "FREQ=DAILY;COUNT=8",
            },
            id="override_new_rrule",
        ),
        pytest.param(
            ALL_DAY_SERIES_ICS.replace(
                "RRULE:FREQ=DAILY;COUNT=5",
                "RRULE:FREQ=DAILY;COUNT=5\nEXDATE;VALUE=DATE:20261122",
            ),
            "all-day-series",
            {"summary": "Holiday", "dtstart": "2026-11-21", "dtend": "2026-11-22"},
            id="exdate_new_start",
        ),
        pytest.param(
            SINGLE_ICS.replace(
                "SUMMARY:Dentist", "RDATE:20261117T150000Z\nSUMMARY:Dentist"
            ),
            "single",
            {
                "summary": "Dentist",
                "dtstart": "2026-11-10T07:00:00",
                "dtend": "2026-11-10T08:00:00",
                "rrule": "FREQ=WEEKLY;COUNT=2",
            },
            id="rdate_new_rrule",
        ),
        pytest.param(
            FIRST_MOVED_ICS,
            "series",
            {
                "summary": "Weekly renamed",
                "dtstart": "2026-10-26T08:00:00",
                "dtend": "2026-10-26T08:30:00",
            },
            id="first_occurrence_moved",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_series_with_exceptions(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    uid: str,
    event: dict[str, Any],
) -> None:
    """Test the start and rule of a series with exceptions can't be changed."""
    response = await _ws_call(
        hass, hass_ws_client, type="calendar/event/update", uid=uid, event=event
    )

    assert response["error"] == {
        "code": "failed",
        "message": (
            "The start and repeat rule of a recurring event with changed or "
            "deleted occurrences can't be changed"
        ),
    }
    stored_event.client.put.assert_not_called()


@pytest.mark.parametrize(
    ("ics", "uid", "event"),
    [
        pytest.param(
            MONDAYS_ICS,
            "mondays",
            {
                "summary": "Planning",
                "dtstart": "2026-11-03T06:00:00",
                "dtend": "2026-11-03T06:30:00",
            },
            id="pinned_days_other_day",
        ),
        pytest.param(
            MONDAYS_ICS,
            "mondays",
            {
                "summary": "Planning",
                "dtstart": "2026-11-03T06:00:00",
                "dtend": "2026-11-03T06:30:00",
                "rrule": "FREQ=WEEKLY;BYDAY=MO;COUNT=4",
            },
            id="pinned_days_other_day_same_rule",
        ),
        pytest.param(
            MONDAYS_ICS.replace("FREQ=WEEKLY;BYDAY=MO", "FREQ=DAILY;BYHOUR=9"),
            "mondays",
            {
                "summary": "Planning",
                "dtstart": "2026-11-02T07:00:00",
                "dtend": "2026-11-02T07:30:00",
            },
            id="pinned_hour_other_time",
        ),
        pytest.param(
            SINGLE_ICS,
            "single",
            {
                "summary": "Dentist",
                "dtstart": "2026-11-10T07:00:00",
                "dtend": "2026-11-10T08:00:00",
                "rrule": "FREQ=WEEKLY;BYDAY=MO",
            },
            id="new_rule_other_day",
        ),
        pytest.param(
            SINGLE_ICS,
            "single",
            {
                "summary": "Dentist",
                "dtstart": "2026-11-10T07:00:00",
                "dtend": "2026-11-10T08:00:00",
                "rrule": "FREQ=DAILY;UNTIL=20261101",
            },
            id="new_rule_ends_before_start",
        ),
        pytest.param(
            NEW_YORK_SERIES_ICS.replace("RRULE:FREQ=WEEKLY;COUNT=8", BROKEN_RULE),
            "series",
            {
                "summary": "Weekly",
                "dtstart": "2026-10-26T10:00:00",
                "dtend": "2026-10-26T10:30:00",
            },
            id="broken_rule",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_series_start_not_in_rule(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    uid: str,
    event: dict[str, Any],
) -> None:
    """Test the start of a series has to be a time its rule produces."""
    response = await _ws_call(
        hass, hass_ws_client, type="calendar/event/update", uid=uid, event=event
    )

    assert response["error"] == {
        "code": "failed",
        "message": (
            "The start of a recurring event has to be one of the times its repeat "
            "rule produces"
        ),
    }
    stored_event.client.put.assert_not_called()


UPDATE_SINGLE = {**UPDATE, "uid": "single"}
DELETE_SINGLE = {**DELETE, "uid": "single"}


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.parametrize(
    "msg", [UPDATE_SINGLE, DELETE_SINGLE], ids=["update", "delete"]
)
@pytest.mark.parametrize(
    ("side_effect", "message"),
    [
        (NotFoundError(), "The event was not found on the CalDAV server"),
        (DAVError(), "Error talking to the CalDAV server"),
        (
            caldav_requests.exceptions.ConnectionError(),
            "Error talking to the CalDAV server",
        ),
    ],
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_event_lookup_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    calendars: list[Mock],
    stored_event: Event,
    msg: dict[str, Any],
    side_effect: Exception,
    message: str,
) -> None:
    """Test errors while looking up the event to change."""
    calendars[0].get_event_by_uid.side_effect = side_effect

    response = await _ws_call(hass, hass_ws_client, **msg)

    assert not response["success"]
    assert response["error"] == {"code": "failed", "message": message}


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.parametrize(
    "msg", [UPDATE_SINGLE, DELETE_SINGLE], ids=["update", "delete"]
)
@pytest.mark.usefixtures("setup_config_entry")
async def test_event_write_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
    msg: dict[str, Any],
) -> None:
    """Test the server refusing a change."""
    stored_event.client.put.return_value.status = 500
    stored_event.client.delete.return_value.status = 500

    response = await _ws_call(hass, hass_ws_client, **msg)

    assert not response["success"]
    assert response["error"] == {
        "code": "failed",
        "message": "Error talking to the CalDAV server",
    }


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_event_sends_etag(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
) -> None:
    """Test an update only overwrites the version that was read."""
    stored_event.props[dav.GetEtag.tag] = '"read-version"'

    response = await _ws_call(hass, hass_ws_client, **UPDATE_SINGLE)

    assert response["success"]
    assert stored_event.client.put.call_args.args[2]["if-match"] == '"read-version"'


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.usefixtures("setup_config_entry")
async def test_update_event_changed_elsewhere(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
) -> None:
    """Test an update fails without retrying when the event changed elsewhere."""
    stored_event.props[dav.GetEtag.tag] = '"read-version"'
    stored_event.client.put.return_value.status = 412

    response = await _ws_call(hass, hass_ws_client, **UPDATE_SINGLE)

    assert response["error"] == {
        "code": "failed",
        "message": "The event was changed on the CalDAV server in the meantime",
    }
    stored_event.client.put.assert_called_once()
    assert stored_event.client.put.call_args.args[2]["if-match"] == '"read-version"'


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.usefixtures("setup_config_entry")
async def test_delete_event_sends_etag(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
) -> None:
    """Test a delete only removes the version that was read."""
    stored_event.props[dav.GetEtag.tag] = '"read-version"'
    # A Schedule-Tag doesn't change for every edit, the ETag does
    stored_event.props[cdav.ScheduleTag.tag] = '"schedule-version"'

    response = await _ws_call(hass, hass_ws_client, **DELETE_SINGLE)

    assert response["success"]
    stored_event.client.delete.assert_called_once_with(
        str(stored_event.url), {"if-match": '"read-version"'}
    )


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.usefixtures("setup_config_entry")
async def test_delete_event_changed_elsewhere(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
) -> None:
    """Test a delete fails without retrying when the event changed elsewhere."""
    stored_event.props[dav.GetEtag.tag] = '"read-version"'
    stored_event.client.delete.return_value.status = 412

    response = await _ws_call(hass, hass_ws_client, **DELETE_SINGLE)

    assert response["error"] == {
        "code": "failed",
        "message": "The event was changed on the CalDAV server in the meantime",
    }
    stored_event.client.delete.assert_called_once()


@pytest.mark.parametrize("ics", [SINGLE_ICS])
@pytest.mark.usefixtures("setup_config_entry")
async def test_delete_event_weak_etag(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    stored_event: Event,
) -> None:
    """Test a weak ETag, which If-Match can't match, gives a plain delete."""
    stored_event.props[dav.GetEtag.tag] = 'W/"read-version"'

    response = await _ws_call(hass, hass_ws_client, **DELETE_SINGLE)

    assert response["success"]
    stored_event.client.delete.assert_called_once_with(str(stored_event.url))
