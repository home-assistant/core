"""The tests for the webdav calendar component."""
from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, Mock

from caldav.objects import Event
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.typing import ClientSessionGenerator

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
def set_tz(hass: HomeAssistant, tz: str | None) -> None:
    """Fixture to set the default TZ to the one requested."""
    if tz is not None:
        hass.config.set_time_zone(tz)


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
            # The start/end times are arbitrary since they are ignored by `_mock_calendar`
            # which just returns all events for the calendar.
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
        events.append(Event(None, "%d.ics" % idx, event, calendar, str(idx)))
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
@freeze_time(_local_datetime(17, 45))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(17, 30))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(17, 00))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(19, 10))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(8, 30))
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
@freeze_time(_local_datetime(12, 00))
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
@freeze_time(_local_datetime(12, 00))
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
@freeze_time(_local_datetime(20, 00))
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
@freeze_time(_local_datetime(12, 00))
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
    """Test that the event lasting the whole day is returned, if it's early in the local day."""
    freezer.move_to(target_datetime.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(21, 45))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(22, 15))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(22, 45))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(23, 15))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(23, 37))
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
    """Test that the recurring all day event is returned early in the local day, and not on the first occurrence."""
    freezer.move_to(target_datetime.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE))
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
    }


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(dt_util.as_local(datetime.datetime(2015, 11, 27, 0, 15)))
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
    }


@pytest.mark.parametrize("tz", ["UTC"])
@freeze_time(dt_util.as_local(datetime.datetime(2015, 11, 27, 11, 15)))
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
            "uid": None,
            "recurrence_id": None,
            "rrule": None,
        }
    ]


@pytest.mark.parametrize(
    ("calendars"),
    [
        [
            _mock_calendar("Calendar 1", supported_components=["VEVENT"]),
            _mock_calendar("Calendar 2", supported_components=["VEVENT", "VJOURNAL"]),
            _mock_calendar("Calendar 3", supported_components=["VTODO"]),
            # Fallback to allow when no components are supported to be conservative
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
    assert state.name == "Calendar 1"
    assert state.state == STATE_OFF

    state = hass.states.get("calendar.calendar_2")
    assert state
    assert state.name == "Calendar 2"
    assert state.state == STATE_OFF

    # No entity created for To-do only component
    state = hass.states.get("calendar.calendar_3")
    assert not state

    state = hass.states.get("calendar.calendar_4")
    assert state
    assert state.name == "Calendar 4"
    assert state.state == STATE_OFF


@pytest.mark.parametrize("tz", [UTC])
@freeze_time(_local_datetime(17, 30))
async def test_setup_config_entry(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test a calendar entity from a config entry."""
    assert await setup_integration()

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
    }
