"""The tests for the webdav calendar component."""

from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
import logging
from typing import Any
from unittest.mock import MagicMock, Mock, patch
import zoneinfo

from caldav.lib.error import DAVError, NotFoundError
from caldav.objects import Event
from freezegun.api import FrozenDateTimeFactory
import icalendar
import pytest

from homeassistant.components.caldav.api import async_get_calendars
from homeassistant.components.calendar import CalendarEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import ClientFixture

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

SUPPORTED_FEATURES = (
    CalendarEntityFeature.CREATE_EVENT
    | CalendarEntityFeature.UPDATE_EVENT
    | CalendarEntityFeature.DELETE_EVENT
)
FILTERED_FEATURES = CalendarEntityFeature.CREATE_EVENT

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


def _local_datetime(hours: int, minutes: int) -> datetime.datetime:
    """Build a datetime object for testing in the correct timezone."""
    return dt_util.as_local(datetime.datetime(2017, 11, 27, hours, minutes, 0))


def _mock_calendar(name: str, supported_components: list[str] | None = None) -> Mock:
    calendar = Mock()
    events = []
    for idx, event in enumerate(EVENTS):
        events.append(Event(None, f"{idx}.ics", event, calendar, str(idx)))
    if supported_components is None:
        supported_components = ["VEVENT"]
    calendar.search = MagicMock(return_value=events)
    calendar.name = name
    calendar.get_supported_components = MagicMock(return_value=supported_components)
    return calendar


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
    assert all_calendar_entities == expected_entities


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
        "supported_features": FILTERED_FEATURES,
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
        "supported_features": FILTERED_FEATURES,
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
        "supported_features": FILTERED_FEATURES,
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
        "supported_features": FILTERED_FEATURES,
    }


@pytest.mark.parametrize(
    ("tz", "target_datetime"),
    [
        # Early
        (UTC, datetime.datetime(2017, 11, 27, 0, 30)),
        (AMERICA_NEW_YORK, datetime.datetime(2017, 11, 27, 0, 30)),
        (ASIA_BAGHDAD, datetime.datetime(2017, 11, 27, 0, 30)),
        # Mid
        (UTC, datetime.datetime(2017, 11, 27, 12, 30)),
        (AMERICA_NEW_YORK, datetime.datetime(2017, 11, 27, 12, 30)),
        (ASIA_BAGHDAD, datetime.datetime(2017, 11, 27, 12, 30)),
        # Late
        (UTC, datetime.datetime(2017, 11, 27, 23, 30)),
        (AMERICA_NEW_YORK, datetime.datetime(2017, 11, 27, 23, 30)),
        (ASIA_BAGHDAD, datetime.datetime(2017, 11, 27, 23, 30)),
    ],
)
async def test_all_day_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    target_datetime: datetime.datetime,
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
        "supported_features": FILTERED_FEATURES,
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
        (UTC, datetime.datetime(2016, 12, 1, 0, 30)),
        (AMERICA_NEW_YORK, datetime.datetime(2016, 12, 1, 0, 30)),
        (ASIA_BAGHDAD, datetime.datetime(2016, 12, 1, 0, 30)),
        # Mid
        (UTC, datetime.datetime(2016, 12, 1, 17, 30)),
        (AMERICA_NEW_YORK, datetime.datetime(2016, 12, 1, 17, 30)),
        (ASIA_BAGHDAD, datetime.datetime(2016, 12, 1, 17, 30)),
        # Late
        (UTC, datetime.datetime(2016, 12, 1, 23, 30)),
        (AMERICA_NEW_YORK, datetime.datetime(2016, 12, 1, 23, 30)),
        (ASIA_BAGHDAD, datetime.datetime(2016, 12, 1, 23, 30)),
    ],
)
async def test_event_rrule_all_day_early(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    target_datetime: datetime.datetime,
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
        "supported_features": FILTERED_FEATURES,
    }


@pytest.mark.parametrize("tz", [UTC])
@pytest.mark.freeze_time(dt_util.as_local(datetime.datetime(2015, 11, 27, 0, 15)))
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
@pytest.mark.freeze_time(dt_util.as_local(datetime.datetime(2015, 11, 27, 11, 15)))
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
        datetime.datetime(2015, 11, 27, 0, 45),
        datetime.datetime(2015, 11, 27, 11, 45),
        datetime.datetime(2015, 11, 27, 12, 15),
    ],
)
async def test_event_rrule_hourly(
    hass: HomeAssistant,
    setup_platform_cb: Callable[[], Awaitable[None]],
    freezer: FrozenDateTimeFactory,
    target_datetime: datetime.datetime,
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
    calendar = Mock()
    calendar.name = "Example"
    calendar.get_supported_components = MagicMock(return_value=["VEVENT"])
    calendar.search = MagicMock(
        return_value=[
            Event(
                None, "0.ics", vevent_with_recurrence_id, calendar, "original-event-uid"
            )
        ]
    )

    with patch(
        "homeassistant.components.caldav.calendar.caldav.DAVClient"
    ) as mock_client:
        mock_client.return_value.principal.return_value.calendars.return_value = [
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
    events = await response.json()

    assert len(events) == 1
    assert events[0]["uid"] == "original-event-uid"
    assert events[0]["recurrence_id"] == "2017-11-27 17:00:00+00:00"
    assert events[0]["summary"] == "Modified occurrence"


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
                "dtend": datetime.datetime(
                    2025, 8, 6, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "dtstart": datetime.datetime(
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
                "dtstart": datetime.datetime(
                    2025, 8, 7, 9, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "dtend": datetime.datetime(
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
                "dtstart": datetime.date(2025, 8, 8),
                "dtend": datetime.date(2025, 8, 9),
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
                "dtstart": datetime.datetime(
                    2025, 8, 7, 7, 0, tzinfo=zoneinfo.ZoneInfo(key="UTC")
                ),
                "dtend": datetime.datetime(
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


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(KeyError(), id="key_error"),
        pytest.param(NotFoundError(), id="not_found_error"),
    ],
)
async def test_missing_supported_components(
    hass: HomeAssistant,
    calendars: list[Mock],
    setup_platform_cb: Callable[[], Awaitable[None]],
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
) -> None:
    """Test setup works when calendar raises on get_supported_components."""
    caplog.set_level(logging.WARNING, logger="homeassistant.components.caldav.api")
    calendars[0].get_supported_components.side_effect = exception
    await setup_platform_cb()

    assert hass.states.get(TEST_ENTITY)

    warning_msg = (
        "CalDAV server does not report supported components for calendar Example, "
        "assuming it supports the requested component 'VEVENT'"
    )
    assert warning_msg in caplog.text

    # Clear caplog and call async_get_calendars again to verify
    # warning is not logged again
    caplog.clear()
    client = MagicMock()
    client.principal().calendars.return_value = calendars

    await async_get_calendars(hass, client, "VEVENT")
    assert warning_msg not in caplog.text

    # Verify that querying a *different* component for the same
    # calendar DOES log the warning again because de-duplication
    # is keyed by (url, component).
    vjournal_warning = (
        "CalDAV server does not report supported components for calendar Example. "
        "Not assuming support for requested component 'VJOURNAL'"
    )
    await async_get_calendars(hass, client, "VJOURNAL")
    assert vjournal_warning in caplog.text


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(KeyError(), id="key_error"),
        pytest.param(NotFoundError(), id="not_found_error"),
    ],
)
async def test_missing_supported_components_not_assumed(
    hass: HomeAssistant,
    calendars: list[Mock],
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
) -> None:
    """Test get_calendars excludes calendars when components unavailable."""
    caplog.set_level(logging.WARNING, logger="homeassistant.components.caldav.api")
    calendars[0].get_supported_components.side_effect = exception
    client = MagicMock()
    client.principal().calendars.return_value = calendars

    returned_calendars = await async_get_calendars(hass, client, "VJOURNAL")

    assert len(returned_calendars) == 0
    warning_msg = (
        "CalDAV server does not report supported components for calendar Example. "
        "Not assuming support for requested component 'VJOURNAL'"
    )
    assert warning_msg in caplog.text

    # Clear caplog and call async_get_calendars again to verify
    # warning is not logged again
    caplog.clear()
    await async_get_calendars(hass, client, "VJOURNAL")
    assert warning_msg not in caplog.text


RECURRING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:Daily standup
END:VEVENT
END:VCALENDAR
"""

UPDATED_EVENT = {
    "summary": "Renamed standup",
    "dtstart": "2017-11-27T17:00:00+00:00",
    "dtend": "2017-11-27T18:00:00+00:00",
}


def _mock_dav_event(calendar: Mock, ics: str = RECURRING_ICS) -> Event:
    """Return a real caldav Event whose writes are captured instead of sent."""
    event = Event(None, "rec-1.ics", ics, calendar, "rec-1")
    event.save = MagicMock()
    event.delete = MagicMock()
    calendar.event_by_uid = MagicMock(return_value=event)
    return event


def _master(event: Event) -> Any:
    return next(
        vevent
        for vevent in event.icalendar_instance.walk("VEVENT")
        if "RECURRENCE-ID" not in vevent
    )


def _overrides(event: Event) -> list[Any]:
    return [
        vevent
        for vevent in event.icalendar_instance.walk("VEVENT")
        if "RECURRENCE-ID" in vevent
    ]


def _saved_tail(calendar: Mock) -> Any:
    """Return the master VEVENT of the object stored for the split-off tail."""
    calendar.save_event.assert_called_once()
    tail = icalendar.Calendar.from_ical(calendar.save_event.call_args[0][0])
    return next(
        vevent for vevent in tail.walk("VEVENT") if "RECURRENCE-ID" not in vevent
    )


async def test_delete_event(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test deleting a whole series."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result("delete", {"entity_id": TEST_ENTITY, "uid": "rec-1"})

    event.delete.assert_called_once()


async def test_delete_event_single_occurrence(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test cancelling one occurrence leaves the series in place."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
        },
    )

    event.delete.assert_not_called()
    master = _master(event)
    assert master["RRULE"].to_ical().decode() == "FREQ=DAILY;COUNT=5"
    assert master["EXDATE"].dts[0].dt == datetime.datetime(
        2017, 11, 28, 17, 0, tzinfo=datetime.UTC
    )


async def test_delete_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test deleting an occurrence onwards caps the series."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    event.delete.assert_not_called()
    recur = _master(event)["RRULE"]
    assert "COUNT" not in recur
    assert recur["UNTIL"][0] == datetime.datetime(
        2017, 11, 29, 16, 59, 59, tzinfo=datetime.UTC
    )


async def test_delete_event_first_occurrence_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that capping at the first occurrence removes the object instead."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-27 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    event.delete.assert_called_once()


async def test_update_event(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test updating a whole series."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "update",
        {"entity_id": TEST_ENTITY, "uid": "rec-1", "event": UPDATED_EVENT},
    )

    event.save.assert_called_once_with(increase_seqno=False, only_this_recurrence=False)
    assert _master(event)["SUMMARY"] == "Renamed standup"
    assert not _overrides(event)


async def test_update_event_single_occurrence(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test editing one occurrence adds an override and leaves the master."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
            "event": UPDATED_EVENT,
        },
    )

    assert _master(event)["SUMMARY"] == "Daily standup"
    overrides = _overrides(event)
    assert len(overrides) == 1
    assert overrides[0]["SUMMARY"] == "Renamed standup"
    assert overrides[0]["RECURRENCE-ID"].dt == datetime.datetime(
        2017, 11, 28, 17, 0, tzinfo=datetime.UTC
    )
    assert "RRULE" not in overrides[0]


async def test_update_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test editing an occurrence onwards splits the series in two."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT
            | {
                "dtstart": "2017-11-29T17:00:00+00:00",
                "dtend": "2017-11-29T18:00:00+00:00",
            },
        },
    )

    recur = _master(event)["RRULE"]
    assert recur["UNTIL"][0] == datetime.datetime(
        2017, 11, 29, 16, 59, 59, tzinfo=datetime.UTC
    )
    assert _master(event)["SUMMARY"] == "Daily standup"

    tail = _saved_tail(calendars[0])
    assert tail["UID"] == "rec-1-20171129T170000Z"
    assert tail["SUMMARY"] == "Renamed standup"
    assert tail["DTSTART"].dt == datetime.datetime(
        2017, 11, 29, 17, 0, tzinfo=datetime.UTC
    )
    # Two occurrences stay in the capped head, so three are left for the tail.
    assert tail["RRULE"]["COUNT"] == [3]


async def test_update_event_not_found(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test an event that is gone from the server surfaces an error."""
    await setup_platform_cb()
    calendars[0].event_by_uid = MagicMock(side_effect=NotFoundError("gone"))

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {"entity_id": TEST_ENTITY, "uid": "missing", "event": UPDATED_EVENT},
    )

    assert not resp["success"]
    assert "Event not found on the server" in resp["error"]["message"]


ALL_DAY_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART;VALUE=DATE:20171127
DTEND;VALUE=DATE:20171128
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:All day standup
END:VEVENT
END:VCALENDAR
"""

OVERRIDDEN_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:Daily standup
END:VEVENT
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
RECURRENCE-ID:20171128T170000Z
DTSTART:20171128T190000Z
DTEND:20171128T200000Z
SUMMARY:Moved standup
END:VEVENT
END:VCALENDAR
"""

NON_RECURRING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
SUMMARY:One off
END:VEVENT
END:VCALENDAR
"""


async def test_update_event_existing_override(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test editing an occurrence that already has an override reuses it."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], OVERRIDDEN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
            "event": UPDATED_EVENT,
        },
    )

    overrides = _overrides(event)
    assert len(overrides) == 1
    assert overrides[0]["SUMMARY"] == "Renamed standup"


async def test_delete_event_drops_stale_override(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that cancelling an occurrence removes its override too."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], OVERRIDDEN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
        },
    )

    assert not _overrides(event)
    assert _master(event)["EXDATE"].dts[0].dt == datetime.datetime(
        2017, 11, 28, 17, 0, tzinfo=datetime.UTC
    )


async def test_delete_all_day_event_single_occurrence(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that an all day EXDATE keeps the DATE value type of DTSTART."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], ALL_DAY_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {"entity_id": TEST_ENTITY, "uid": "rec-1", "recurrence_id": "2017-11-28"},
    )

    assert _master(event)["EXDATE"].dts[0].dt == datetime.date(2017, 11, 28)


async def test_delete_all_day_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that an all day UNTIL is a date on the day before the occurrence."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], ALL_DAY_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    assert _master(event)["RRULE"]["UNTIL"][0] == datetime.date(2017, 11, 28)


async def test_delete_event_not_recurring(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test scoping to future occurrences of an event that does not recur."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0], NON_RECURRING_ICS)

    client = await ws_client()
    resp = await client.cmd(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    assert not resp["success"]
    assert "not a recurring series" in resp["error"]["message"]


async def test_delete_event_invalid_recurrence_id(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test a recurrence id that cannot be parsed."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0])

    client = await ws_client()
    resp = await client.cmd(
        "delete",
        {"entity_id": TEST_ENTITY, "uid": "rec-1", "recurrence_id": "not-a-date"},
    )

    assert not resp["success"]
    assert "Unable to parse recurrence id" in resp["error"]["message"]


async def test_update_event_first_occurrence_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that scoping from the first occurrence edits the series in place."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-27 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    calendars[0].save_event.assert_not_called()
    master = _master(event)
    assert master["SUMMARY"] == "Renamed standup"
    assert master["RRULE"].to_ical().decode() == "FREQ=DAILY;COUNT=5"


FLOATING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000
DTEND:20171127T180000
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:Floating standup
END:VEVENT
END:VCALENDAR
"""


async def test_update_event_keeps_recurrence(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that an update without an rrule leaves the series recurring.

    The coordinator expands recurring events, so CalendarEvent.rrule is never
    populated and the frontend cannot echo the rule back on an ordinary edit.
    """
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "update",
        {"entity_id": TEST_ENTITY, "uid": "rec-1", "event": UPDATED_EVENT},
    )

    master = _master(event)
    assert master["SUMMARY"] == "Renamed standup"
    assert master["RRULE"].to_ical().decode() == "FREQ=DAILY;COUNT=5"


async def test_update_event_this_and_future_creates_tail_first(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a failure to store the tail leaves the series untouched."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])
    calendars[0].save_event = MagicMock(side_effect=DAVError("boom"))

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    assert not resp["success"]
    event.save.assert_not_called()
    assert _master(event)["RRULE"].to_ical().decode() == "FREQ=DAILY;COUNT=5"


async def test_delete_floating_event_single_occurrence(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a floating series gets a floating EXDATE."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], FLOATING_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00",
        },
    )

    exdate = _master(event)["EXDATE"].dts[0].dt
    assert exdate == datetime.datetime(2017, 11, 28, 17, 0)
    assert exdate.tzinfo is None


async def test_delete_floating_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a floating series gets a floating UNTIL, as RFC 5545 requires."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], FLOATING_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    until = _master(event)["RRULE"]["UNTIL"][0]
    assert until == datetime.datetime(2017, 11, 29, 16, 59, 59)
    assert until.tzinfo is None


RICH_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:STANDARD
DTSTART:19701025T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART;TZID=Europe/Berlin:20171127T170000
DTEND;TZID=Europe/Berlin:20171127T180000
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:Daily standup
ORGANIZER:mailto:boss@example.com
ATTENDEE:mailto:dev@example.com
CATEGORIES:work
X-CUSTOM-PROP:keep-me
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT10M
END:VALARM
END:VEVENT
END:VCALENDAR
"""

MIXED_RDATE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
RRULE:FREQ=DAILY;COUNT=3
RDATE:20171201T170000Z,20171203T170000Z
SUMMARY:Mixed series
END:VEVENT
END:VCALENDAR
"""

RDATE_ONLY_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
RDATE:20171129T170000Z
RDATE:20171201T170000Z
SUMMARY:Extra sessions
END:VEVENT
END:VCALENDAR
"""


async def test_update_event_this_and_future_preserves_master_data(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that the split-off tail keeps properties the edit cannot carry."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0], RICH_ICS)
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 16:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    stored = icalendar.Calendar.from_ical(calendars[0].save_event.call_args[0][0])
    assert any(item.name == "VTIMEZONE" for item in stored.subcomponents)
    tail = _saved_tail(calendars[0])
    assert tail["SUMMARY"] == "Renamed standup"
    assert str(tail["ORGANIZER"]) == "mailto:boss@example.com"
    assert str(tail["ATTENDEE"]) == "mailto:dev@example.com"
    assert tail["X-CUSTOM-PROP"] == "keep-me"
    assert any(item.name == "VALARM" for item in tail.subcomponents)


async def test_update_event_this_and_future_rolls_back_tail(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a failure to cap the head removes the stored tail again."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])
    fresh = Event(None, "rec-1.ics", RECURRING_ICS, calendars[0], "rec-1")
    calendars[0].event_by_uid = MagicMock(side_effect=[event, fresh])
    tail = Mock()
    calendars[0].save_event = MagicMock(return_value=tail)
    event.save.side_effect = DAVError("boom")

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    assert not resp["success"]
    tail.delete.assert_called_once()


async def test_update_event_not_recurring(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that scoping an update to future occurrences needs a series."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], NON_RECURRING_ICS)

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    assert not resp["success"]
    assert "not a recurring series" in resp["error"]["message"]
    calendars[0].save_event.assert_not_called()
    event.save.assert_not_called()


async def test_delete_event_this_and_future_drops_future_rdates(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that the cutoff applies to RDATEs as well as the rule."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], MIXED_RDATE_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-12-03 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    master = _master(event)
    # The rule ends before the cutoff; an UNTIL there would add occurrences.
    assert master["RRULE"].to_ical().decode() == "FREQ=DAILY;COUNT=3"
    assert [item.dt for item in master["RDATE"].dts] == [
        datetime.datetime(2017, 12, 1, 17, 0, tzinfo=datetime.UTC)
    ]


async def test_delete_rdate_only_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a series recurring only through RDATEs can be capped."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], RDATE_ONLY_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-12-01 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    master = _master(event)
    assert "RRULE" not in master
    assert [item.dt for item in master["RDATE"].dts] == [
        datetime.datetime(2017, 11, 29, 17, 0, tzinfo=datetime.UTC)
    ]


async def test_update_rdate_only_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that splitting a series recurring only through RDATEs works."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], RDATE_ONLY_ICS)
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-12-01 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": {
                "summary": "Renamed session",
                "dtstart": "2017-12-01T17:00:00+00:00",
                "dtend": "2017-12-01T18:00:00+00:00",
            },
        },
    )

    tail = _saved_tail(calendars[0])
    assert "RRULE" not in tail
    assert [item.dt for item in tail["RDATE"].dts] == [
        datetime.datetime(2017, 12, 1, 17, 0, tzinfo=datetime.UTC)
    ]
    assert [item.dt for item in _master(event)["RDATE"].dts] == [
        datetime.datetime(2017, 11, 29, 17, 0, tzinfo=datetime.UTC)
    ]


@pytest.mark.parametrize(
    ("tz", "config"),
    [
        (
            UTC,
            {
                "custom_calendars": [
                    {"name": CALENDAR_NAME, "calendar": CALENDAR_NAME, "search": ".*"}
                ]
            },
        )
    ],
)
async def test_filtered_entity_does_not_expose_writes(
    hass: HomeAssistant,
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a filtered entity cannot reach events it never shows."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0])

    state = hass.states.get("calendar.example_example")
    assert state
    assert state.attributes["supported_features"] == FILTERED_FEATURES

    client = await ws_client()
    resp = await client.cmd(
        "delete", {"entity_id": "calendar.example_example", "uid": "rec-1"}
    )
    assert not resp["success"]


async def test_update_event_changes_recurrence(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a passed rrule replaces the rule of the series."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": UPDATED_EVENT | {"rrule": "FREQ=WEEKLY"},
        },
    )

    assert _master(event)["RRULE"].to_ical().decode() == "FREQ=WEEKLY"


async def test_update_all_day_event_this_and_future(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that an all day split reduces COUNT by the days the head keeps."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0], ALL_DAY_ICS)
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29",
            "recurrence_range": "THISANDFUTURE",
            "event": {
                "summary": "Renamed standup",
                "dtstart": "2017-11-29",
                "dtend": "2017-11-30",
            },
        },
    )

    tail = _saved_tail(calendars[0])
    assert tail["RRULE"]["COUNT"] == [3]


async def test_update_event_this_and_future_drops_tail_overrides(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that the tail does not carry overrides of the old series."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0], OVERRIDDEN_ICS)
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    stored = icalendar.Calendar.from_ical(calendars[0].save_event.call_args[0][0])
    assert len(list(stored.walk("VEVENT"))) == 1


async def test_update_event_this_and_future_rollback_failure(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failing rollback still reports the original error."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])
    fresh = Event(None, "rec-1.ics", RECURRING_ICS, calendars[0], "rec-1")
    calendars[0].event_by_uid = MagicMock(side_effect=[event, fresh])
    tail = Mock()
    tail.delete.side_effect = DAVError("still down")
    calendars[0].save_event = MagicMock(return_value=tail)
    event.save.side_effect = DAVError("boom")

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    assert not resp["success"]
    assert "boom" in resp["error"]["message"]
    assert "could not be removed" in caplog.text


CAPPED_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
RRULE:FREQ=DAILY;UNTIL=20171129T165959Z
SUMMARY:Daily standup
END:VEVENT
END:VCALENDAR
"""


async def test_update_event_keeps_start_anchor(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a summary-only edit does not re-anchor the start time."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], RICH_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": {
                "summary": "Renamed standup",
                "dtstart": "2017-11-27T16:00:00+00:00",
                "dtend": "2017-11-27T17:00:00+00:00",
            },
        },
    )

    dtstart = _master(event)["DTSTART"]
    assert dtstart.dt == datetime.datetime(
        2017, 11, 27, 17, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
    )
    assert str(dtstart.dt.tzinfo) == "Europe/Berlin"


@pytest.mark.parametrize("tz", [UTC])
async def test_update_event_moves_floating_start(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a moved time on a floating series stays floating."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], FLOATING_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": {
                "summary": "Floating standup",
                "dtstart": "2017-11-27T18:00:00+00:00",
                "dtend": "2017-11-27T19:00:00+00:00",
            },
        },
    )

    dtstart = _master(event)["DTSTART"].dt
    assert dtstart == datetime.datetime(2017, 11, 27, 18, 0)
    assert dtstart.tzinfo is None


async def test_update_event_this_and_future_replayed(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that replaying a finished split does not clone the capped head."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], CAPPED_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    calendars[0].save_event.assert_not_called()
    event.save.assert_not_called()


async def test_update_event_first_occurrence_drops_overrides(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that an edit of every future occurrence clears old overrides."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], OVERRIDDEN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-27 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    assert _master(event)["SUMMARY"] == "Renamed standup"
    assert not _overrides(event)


async def test_update_event_this_and_future_ambiguous_failure(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the tail survives when the head state cannot be verified."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])
    calendars[0].event_by_uid = MagicMock(side_effect=[event, DAVError("down")])
    tail = Mock()
    calendars[0].save_event = MagicMock(return_value=tail)
    event.save.side_effect = DAVError("boom")

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-29 17:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": UPDATED_EVENT,
        },
    )

    assert not resp["success"]
    tail.delete.assert_not_called()
    assert "Keeping the split-off series" in caplog.text


MIXED_TZ_EXDATE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:STANDARD
DTSTART:19701025T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
DTSTART;TZID=Europe/Berlin:20171127T170000
DTEND;TZID=Europe/Berlin:20171127T180000
RRULE:FREQ=DAILY;COUNT=10
EXDATE;TZID=Europe/Berlin:20171128T170000,20171204T170000
EXDATE:20171129T160000Z
SUMMARY:Daily standup
END:VEVENT
END:VCALENDAR
"""


async def test_delete_event_this_and_future_keeps_exdate_zones(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that filtering EXDATEs does not merge lines with different zones."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], MIXED_TZ_EXDATE_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-12-01 16:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
        },
    )

    entries = _master(event)["EXDATE"]
    assert isinstance(entries, list)
    berlin, utc = entries
    assert berlin.params["TZID"] == "Europe/Berlin"
    assert [item.dt for item in berlin.dts] == [
        datetime.datetime(
            2017, 11, 28, 17, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
        )
    ]
    assert [item.dt for item in utc.dts] == [
        datetime.datetime(2017, 11, 29, 16, 0, tzinfo=datetime.UTC)
    ]


async def test_update_event_new_rrule_drops_overrides(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that replacing the rule clears overrides of the old series."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], OVERRIDDEN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": UPDATED_EVENT | {"rrule": "FREQ=WEEKLY"},
        },
    )

    assert not _overrides(event)


async def test_update_event_single_occurrence_ignores_rrule(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a rule in the payload cannot make an override recurring."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
            "event": UPDATED_EVENT | {"rrule": "FREQ=WEEKLY"},
        },
    )

    (override,) = _overrides(event)
    assert "RRULE" not in override
    assert _master(event)["RRULE"].to_ical().decode() == "FREQ=DAILY;COUNT=5"


async def test_update_event_rejects_all_day_toggle(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a series cannot switch between timed and all day."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0])

    client = await ws_client()
    resp = await client.cmd(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": {
                "summary": "Renamed standup",
                "dtstart": "2017-11-27",
                "dtend": "2017-11-28",
            },
        },
    )

    assert not resp["success"]
    assert "all-day" in resp["error"]["message"]
    event.save.assert_not_called()


async def test_update_event_single_occurrence_keeps_master_data(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a new override inherits what the edit cannot carry."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], RICH_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 16:00:00+00:00",
            "event": UPDATED_EVENT,
        },
    )

    (override,) = _overrides(event)
    assert str(override["ATTENDEE"]) == "mailto:dev@example.com"
    assert any(item.name == "VALARM" for item in override.subcomponents)
    assert "RRULE" not in override


ORPHAN_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
RECURRENCE-ID:20171128T170000Z
DTSTART:20171128T190000Z
DTEND:20171128T200000Z
SUMMARY:Orphan override
END:VEVENT
END:VCALENDAR
"""


async def test_update_orphan_override(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that editing an object holding only an override keeps it."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], ORPHAN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": UPDATED_EVENT
            | {
                "dtstart": "2017-11-28T20:00:00+00:00",
                "dtend": "2017-11-28T21:00:00+00:00",
            },
        },
    )

    vevents = list(event.icalendar_instance.walk("VEVENT"))
    assert len(vevents) == 1
    assert vevents[0]["SUMMARY"] == "Renamed standup"


async def test_delete_occurrence_of_orphan_override(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that cancelling the orphan's only occurrence drops the resource."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], ORPHAN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
        },
    )

    event.delete.assert_called_once()


TWO_ORPHANS_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
RECURRENCE-ID:20171128T170000Z
DTSTART:20171128T190000Z
DTEND:20171128T200000Z
SUMMARY:First orphan
END:VEVENT
BEGIN:VEVENT
UID:rec-1
DTSTAMP:20171125T000000Z
RECURRENCE-ID:20171129T170000Z
DTSTART:20171129T190000Z
DTEND:20171129T200000Z
SUMMARY:Second orphan
END:VEVENT
END:VCALENDAR
"""


async def test_delete_one_of_two_orphan_overrides(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that deleting one orphan occurrence keeps the other."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], TWO_ORPHANS_ICS)

    client = await ws_client()
    await client.cmd_result(
        "delete",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-28 17:00:00+00:00",
        },
    )

    event.delete.assert_not_called()
    vevents = list(event.icalendar_instance.walk("VEVENT"))
    assert [vevent["SUMMARY"] for vevent in vevents] == ["Second orphan"]


async def test_update_event_same_rrule_keeps_overrides(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that resubmitting the unchanged rule keeps overrides."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], OVERRIDDEN_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": UPDATED_EVENT | {"rrule": "FREQ=DAILY;COUNT=5"},
        },
    )

    assert len(_overrides(event)) == 1


async def test_update_event_new_rrule_drops_exdates(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a new rule clears dates anchored to the old schedule."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], MIXED_TZ_EXDATE_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "event": {
                "summary": "Renamed standup",
                "dtstart": "2017-11-27T16:00:00+00:00",
                "dtend": "2017-11-27T17:00:00+00:00",
                "rrule": "FREQ=WEEKLY",
            },
        },
    )

    master = _master(event)
    assert "EXDATE" not in master
    assert master["RRULE"].to_ical().decode() == "FREQ=WEEKLY"


async def test_update_event_first_occurrence_new_rule_drops_exdates(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that rescheduling every future occurrence clears old exceptions."""
    await setup_platform_cb()
    event = _mock_dav_event(calendars[0], MIXED_TZ_EXDATE_ICS)

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-11-27 16:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": {
                "summary": "Renamed standup",
                "dtstart": "2017-11-27T17:00:00+00:00",
                "dtend": "2017-11-27T18:00:00+00:00",
            },
        },
    )

    assert "EXDATE" not in _master(event)


async def test_update_event_moved_tail_drops_exdates(
    setup_platform_cb: Callable[[], Awaitable[None]],
    calendars: list[Mock],
    ws_client: ClientFixture,
) -> None:
    """Test that a moved tail does not carry dates of the old schedule."""
    await setup_platform_cb()
    _mock_dav_event(calendars[0], MIXED_TZ_EXDATE_ICS)
    calendars[0].save_event = MagicMock(return_value=Mock())

    client = await ws_client()
    await client.cmd_result(
        "update",
        {
            "entity_id": TEST_ENTITY,
            "uid": "rec-1",
            "recurrence_id": "2017-12-01 16:00:00+00:00",
            "recurrence_range": "THISANDFUTURE",
            "event": {
                "summary": "Renamed standup",
                "dtstart": "2017-12-01T18:00:00+00:00",
                "dtend": "2017-12-01T19:00:00+00:00",
            },
        },
    )

    tail = _saved_tail(calendars[0])
    assert "EXDATE" not in tail
