"""The tests for the webdav calendar component."""
import datetime
from http import HTTPStatus
from unittest.mock import MagicMock, Mock, patch

from caldav.objects import Event
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

DEVICE_DATA = {"name": "Private Calendar", "device_id": "Private Calendar"}

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


@pytest.fixture
def set_tz(request):
    """Set the default TZ to the one requested."""
    return request.getfixturevalue(request.param)


@pytest.fixture
def utc(hass):
    """Set the default TZ to UTC."""
    hass.config.set_time_zone("UTC")


@pytest.fixture
def new_york(hass):
    """Set the default TZ to America/New_York."""
    hass.config.set_time_zone("America/New_York")


@pytest.fixture
def baghdad(hass):
    """Set the default TZ to Asia/Baghdad."""
    hass.config.set_time_zone("Asia/Baghdad")


@pytest.fixture(autouse=True)
def mock_http(hass):
    """Mock the http component."""
    hass.http = Mock()


@pytest.fixture
def mock_dav_client():
    """Mock the dav client."""
    patch_dav_client = patch(
        "caldav.DAVClient", return_value=_mocked_dav_client("First", "Second")
    )
    with patch_dav_client as dav_client:
        yield dav_client


@pytest.fixture(name="calendar")
def mock_private_cal():
    """Mock a private calendar."""
    _calendar = _mock_calendar("Private")
    calendars = [_calendar]
    client = _mocked_dav_client(calendars=calendars)
    patch_dav_client = patch("caldav.DAVClient", return_value=client)
    with patch_dav_client:
        yield _calendar


@pytest.fixture
def get_api_events(hass_client):
    """Fixture to return events for a specific calendar using the API."""

    async def api_call(entity_id):
        client = await hass_client()
        response = await client.get(
            # The start/end times are arbitrary since they are ignored by `_mock_calendar`
            # which just returns all events for the calendar.
            f"/api/calendars/{entity_id}?start=2022-01-01&end=2022-01-01"
        )
        assert response.status == HTTPStatus.OK
        return await response.json()

    return api_call


def _local_datetime(hours, minutes):
    """Build a datetime object for testing in the correct timezone."""
    return dt.as_local(datetime.datetime(2017, 11, 27, hours, minutes, 0))


def _mocked_dav_client(*names, calendars=None):
    """Mock requests.get invocations."""
    if calendars is None:
        calendars = [_mock_calendar(name) for name in names]
    principal = Mock()
    principal.calendars = MagicMock(return_value=calendars)

    client = Mock()
    client.principal = MagicMock(return_value=principal)
    return client


def _mock_calendar(name):
    calendar = Mock()
    events = []
    for idx, event in enumerate(EVENTS):
        events.append(Event(None, "%d.ics" % idx, event, calendar, str(idx)))

    calendar.search = MagicMock(return_value=events)
    calendar.name = name
    return calendar


async def test_setup_component(hass: HomeAssistant, mock_dav_client) -> None:
    """Test setup component with calendars."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.first")
    assert state.name == "First"
    state = hass.states.get("calendar.second")
    assert state.name == "Second"


async def test_setup_component_with_no_calendar_matching(
    hass: HomeAssistant, mock_dav_client
) -> None:
    """Test setup component with wrong calendar."""
    config = dict(CALDAV_CONFIG)
    config["calendars"] = ["none"]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    all_calendar_states = hass.states.async_entity_ids("calendar")
    assert not all_calendar_states


async def test_setup_component_with_a_calendar_match(
    hass: HomeAssistant, mock_dav_client
) -> None:
    """Test setup component with right calendar."""
    config = dict(CALDAV_CONFIG)
    config["calendars"] = ["Second"]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    all_calendar_states = hass.states.async_entity_ids("calendar")
    assert len(all_calendar_states) == 1
    state = hass.states.get("calendar.second")
    assert state.name == "Second"


async def test_setup_component_with_one_custom_calendar(
    hass: HomeAssistant, mock_dav_client
) -> None:
    """Test setup component with custom calendars."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "HomeOffice", "calendar": "Second", "search": "HomeOffice"}
    ]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    all_calendar_states = hass.states.async_entity_ids("calendar")
    assert len(all_calendar_states) == 1
    state = hass.states.get("calendar.second_homeoffice")
    assert state.name == "HomeOffice"


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(17, 45))
async def test_ongoing_event(mock_now, hass: HomeAssistant, calendar, set_tz) -> None:
    """Test that the ongoing event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(17, 30))
async def test_just_ended_event(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the next ongoing event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(17, 00))
async def test_ongoing_event_different_tz(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the ongoing event with another timezone is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "Enjoy the sun",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 16:30:00",
        "description": "Sunny day",
        "end_time": "2017-11-27 17:30:00",
        "location": "San Francisco",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(19, 10))
async def test_ongoing_floating_event_returned(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that floating events without timezones work."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a floating Event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 19:00:00",
        "end_time": "2017-11-27 20:00:00",
        "location": "Hamburg",
        "description": "What a day",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(8, 30))
async def test_ongoing_event_with_offset(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the offset is taken into account."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is an offset event",
        "all_day": False,
        "offset_reached": True,
        "start_time": "2017-11-27 10:00:00",
        "end_time": "2017-11-27 11:00:00",
        "location": "Hamburg",
        "description": "Surprisingly shiny",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(12, 00))
async def test_matching_filter(mock_now, hass: HomeAssistant, calendar, set_tz) -> None:
    """Test that the matching event is returned."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": "This is a normal event"}
    ]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private_private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(12, 00))
async def test_matching_filter_real_regexp(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the event matching the regexp is returned."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": r".*rainy"}
    ]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private_private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@patch("homeassistant.util.dt.now", return_value=_local_datetime(20, 00))
async def test_filter_matching_past_event(
    mock_now, hass: HomeAssistant, calendar
) -> None:
    """Test that the matching past event is not returned."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": "This is a normal event"}
    ]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private_private")
    assert state.name == calendar.name
    assert state.state == "off"


@patch("homeassistant.util.dt.now", return_value=_local_datetime(12, 00))
async def test_no_result_with_filtering(
    mock_now, hass: HomeAssistant, calendar
) -> None:
    """Test that nothing is returned since nothing matches."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {
            "name": "Private",
            "calendar": "Private",
            "search": "This is a non-existing event",
        }
    ]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private_private")
    assert state.name == calendar.name
    assert state.state == "off"


async def _day_event_returned(hass, calendar, config, date_time):
    with patch("homeassistant.util.dt.now", return_value=date_time):
        assert await async_setup_component(hass, "calendar", {"calendar": config})
        await hass.async_block_till_done()

        state = hass.states.get("calendar.private_private")
        assert state.name == calendar.name
        assert state.state == STATE_ON
        assert dict(state.attributes) == {
            "friendly_name": "Private",
            "message": "This is an all day event",
            "all_day": True,
            "offset_reached": False,
            "start_time": "2017-11-27 00:00:00",
            "end_time": "2017-11-28 00:00:00",
            "location": "Hamburg",
            "description": "What a beautiful day",
        }


@pytest.mark.parametrize("set_tz", ["utc", "new_york", "baghdad"], indirect=True)
async def test_all_day_event_returned_early(
    hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the event lasting the whole day is returned, if it's early in the local day."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": ".*"}
    ]

    await _day_event_returned(
        hass,
        calendar,
        config,
        datetime.datetime(2017, 11, 27, 0, 30).replace(tzinfo=dt.DEFAULT_TIME_ZONE),
    )


@pytest.mark.parametrize("set_tz", ["utc", "new_york", "baghdad"], indirect=True)
async def test_all_day_event_returned_mid(
    hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the event lasting the whole day is returned, if it's in the middle of the local day."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": ".*"}
    ]

    await _day_event_returned(
        hass,
        calendar,
        config,
        datetime.datetime(2017, 11, 27, 12, 30).replace(tzinfo=dt.DEFAULT_TIME_ZONE),
    )


@pytest.mark.parametrize("set_tz", ["utc", "new_york", "baghdad"], indirect=True)
async def test_all_day_event_returned_late(
    hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the event lasting the whole day is returned, if it's late in the local day."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": ".*"}
    ]

    await _day_event_returned(
        hass,
        calendar,
        config,
        datetime.datetime(2017, 11, 27, 23, 30).replace(tzinfo=dt.DEFAULT_TIME_ZONE),
    )


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(21, 45))
async def test_event_rrule(mock_now, hass: HomeAssistant, calendar, set_tz) -> None:
    """Test that the future recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 22:00:00",
        "end_time": "2017-11-27 22:30:00",
        "location": "Hamburg",
        "description": "Every day for a while",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(22, 15))
async def test_event_rrule_ongoing(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the current recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 22:00:00",
        "end_time": "2017-11-27 22:30:00",
        "location": "Hamburg",
        "description": "Every day for a while",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(22, 45))
async def test_event_rrule_duration(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the future recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a recurring event with a duration",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 23:00:00",
        "end_time": "2017-11-27 23:30:00",
        "location": "Hamburg",
        "description": "Every day for a while as well",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(23, 15))
async def test_event_rrule_duration_ongoing(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the ongoing recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a recurring event with a duration",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 23:00:00",
        "end_time": "2017-11-27 23:30:00",
        "location": "Hamburg",
        "description": "Every day for a while as well",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch("homeassistant.util.dt.now", return_value=_local_datetime(23, 37))
async def test_event_rrule_endless(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the endless recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a recurring event that never ends",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 23:45:00",
        "end_time": "2017-11-27 23:59:59",
        "location": "Hamburg",
        "description": "Every day forever",
    }


async def _event_rrule_all_day(hass, calendar, config, date_time):
    with patch("homeassistant.util.dt.now", return_value=date_time):
        assert await async_setup_component(hass, "calendar", {"calendar": config})
        await hass.async_block_till_done()

        state = hass.states.get("calendar.private_private")
        assert state.name == calendar.name
        assert state.state == STATE_ON
        assert dict(state.attributes) == {
            "friendly_name": "Private",
            "message": "This is a recurring all day event",
            "all_day": True,
            "offset_reached": False,
            "start_time": "2016-12-01 00:00:00",
            "end_time": "2016-12-02 00:00:00",
            "location": "Hamburg",
            "description": "Groundhog Day",
        }


@pytest.mark.parametrize("set_tz", ["utc", "new_york", "baghdad"], indirect=True)
async def test_event_rrule_all_day_early(hass: HomeAssistant, calendar, set_tz) -> None:
    """Test that the recurring all day event is returned early in the local day, and not on the first occurrence."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": ".*"}
    ]

    await _event_rrule_all_day(
        hass,
        calendar,
        config,
        datetime.datetime(2016, 12, 1, 0, 30).replace(tzinfo=dt.DEFAULT_TIME_ZONE),
    )


@pytest.mark.parametrize("set_tz", ["utc", "new_york", "baghdad"], indirect=True)
async def test_event_rrule_all_day_mid(hass: HomeAssistant, calendar, set_tz) -> None:
    """Test that the recurring all day event is returned in the middle of the local day, and not on the first occurrence."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": ".*"}
    ]

    await _event_rrule_all_day(
        hass,
        calendar,
        config,
        datetime.datetime(2016, 12, 1, 17, 30).replace(tzinfo=dt.DEFAULT_TIME_ZONE),
    )


@pytest.mark.parametrize("set_tz", ["utc", "new_york", "baghdad"], indirect=True)
async def test_event_rrule_all_day_late(hass: HomeAssistant, calendar, set_tz) -> None:
    """Test that the recurring all day event is returned late in the local day, and not on the first occurrence."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": ".*"}
    ]

    await _event_rrule_all_day(
        hass,
        calendar,
        config,
        datetime.datetime(2016, 12, 1, 23, 30).replace(tzinfo=dt.DEFAULT_TIME_ZONE),
    )


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch(
    "homeassistant.util.dt.now",
    return_value=dt.as_local(datetime.datetime(2015, 11, 27, 0, 15)),
)
async def test_event_rrule_hourly_on_first(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the endless recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is an hourly recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2015-11-27 00:00:00",
        "end_time": "2015-11-27 00:30:00",
        "location": "Hamburg",
        "description": "The bell tolls for thee",
    }


@pytest.mark.parametrize("set_tz", ["utc"], indirect=True)
@patch(
    "homeassistant.util.dt.now",
    return_value=dt.as_local(datetime.datetime(2015, 11, 27, 11, 15)),
)
async def test_event_rrule_hourly_on_last(
    mock_now, hass: HomeAssistant, calendar, set_tz
) -> None:
    """Test that the endless recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is an hourly recurring event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2015-11-27 11:00:00",
        "end_time": "2015-11-27 11:30:00",
        "location": "Hamburg",
        "description": "The bell tolls for thee",
    }


@patch(
    "homeassistant.util.dt.now",
    return_value=dt.as_local(datetime.datetime(2015, 11, 27, 0, 45)),
)
async def test_event_rrule_hourly_off_first(
    mock_now, hass: HomeAssistant, calendar
) -> None:
    """Test that the endless recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF


@patch(
    "homeassistant.util.dt.now",
    return_value=dt.as_local(datetime.datetime(2015, 11, 27, 11, 45)),
)
async def test_event_rrule_hourly_off_last(
    mock_now, hass: HomeAssistant, calendar
) -> None:
    """Test that the endless recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF


@patch(
    "homeassistant.util.dt.now",
    return_value=dt.as_local(datetime.datetime(2015, 11, 27, 12, 15)),
)
async def test_event_rrule_hourly_ended(
    mock_now, hass: HomeAssistant, calendar
) -> None:
    """Test that the endless recurring event is returned."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get("calendar.private")
    assert state.name == calendar.name
    assert state.state == STATE_OFF


async def test_get_events(hass: HomeAssistant, calendar, get_api_events) -> None:
    """Test that all events are returned on API."""
    assert await async_setup_component(hass, "calendar", {"calendar": CALDAV_CONFIG})
    await hass.async_block_till_done()

    events = await get_api_events("calendar.private")
    assert len(events) == 18
    assert calendar.call


async def test_get_events_custom_calendars(
    hass: HomeAssistant, calendar, get_api_events
) -> None:
    """Test that only searched events are returned on API."""
    config = dict(CALDAV_CONFIG)
    config["custom_calendars"] = [
        {"name": "Private", "calendar": "Private", "search": "This is a normal event"}
    ]

    assert await async_setup_component(hass, "calendar", {"calendar": config})
    await hass.async_block_till_done()

    events = await get_api_events("calendar.private_private")
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
