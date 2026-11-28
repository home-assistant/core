"""Tests for the CalDAV actions."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

from caldav.calendarobjectresource import FreeBusy
from caldav.lib.error import DAVError, ReportError
from caldav.lib.http_sync import requests as caldav_requests
from caldav.lib.url import URL
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.caldav.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

SERVICE_GET_FREE_BUSY = "get_free_busy"
TEST_ENTITY = "calendar.example"
START = "2026-11-29 00:00:00"
END = "2026-11-30 00:00:00"

FREE_BUSY_LINES = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sabre//Sabre VObject 4.5.6//EN
BEGIN:VFREEBUSY
DTSTART:20261129T080000Z
DTEND:20261130T080000Z
DTSTAMP:20261127T120000Z
FREEBUSY:20261129T170000Z/20261129T180000Z,20261129T200000Z/PT30M
FREEBUSY;FBTYPE=BUSY-TENTATIVE:20261129T173000Z/20261129T190000Z
FREEBUSY;FBTYPE=FREE:20261129T220000Z/20261129T230000Z
FREEBUSY;FBTYPE=BUSY-UNAVAILABLE:20261129T090000Z/20261129T100000Z
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_COMPONENTS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PYVOBJECT//NONSGML Version 0.9.9//EN
BEGIN:VFREEBUSY
DTSTART:20261129T170000Z
DTEND:20261129T180000Z
FBTYPE:BUSY
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261129T200000Z
DTEND:20261129T203000Z
FBTYPE:BUSY
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261129T173000Z
DTEND:20261129T190000Z
FBTYPE:BUSY-TENTATIVE
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261129T220000Z
DTEND:20261129T230000Z
FBTYPE:FREE
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261129T090000Z
DTEND:20261129T100000Z
FBTYPE:BUSY-UNAVAILABLE
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_SINGLE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sabre//Sabre VObject 4.5.6//EN
BEGIN:VFREEBUSY
DTSTART:20261129T080000Z
DTEND:20261130T080000Z
DTSTAMP:20261127T120000Z
FREEBUSY:20261129T170000Z/20261129T180000Z
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_TOUCHING_CONTAINED = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PYVOBJECT//NONSGML Version 0.9.9//EN
BEGIN:VFREEBUSY
DTSTART:20261129T170000Z
DTEND:20261129T200000Z
FBTYPE:busy
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261129T180000Z
DTEND:20261129T190000Z
FBTYPE:busy
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261129T200000Z
DTEND:20261129T203000Z
FBTYPE:busy
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_BEYOND_RANGE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PYVOBJECT//NONSGML Version 0.9.9//EN
BEGIN:VFREEBUSY
DTSTART:20261129T060000Z
DTEND:20261129T090000Z
FBTYPE:BUSY
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261130T070000Z
DTEND:20261130T100000Z
FBTYPE:BUSY
END:VFREEBUSY
BEGIN:VFREEBUSY
DTSTART:20261130T090000Z
DTEND:20261130T100000Z
FBTYPE:BUSY
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_ZERO_LENGTH = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Xandikos//EN
BEGIN:VFREEBUSY
DTSTART:20261129T080000Z
DTEND:20261130T080000Z
DTSTAMP:20261127T120000Z
FREEBUSY:20261129T180000Z/20261129T180000Z
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_NOTHING = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sabre//Sabre VObject 4.5.6//EN
BEGIN:VFREEBUSY
DTSTART:20261129T080000Z
DTEND:20261130T080000Z
DTSTAMP:20261127T120000Z
END:VFREEBUSY
END:VCALENDAR
"""
FREE_BUSY_NO_COMPONENT = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//PYVOBJECT//NONSGML Version 0.9.9//EN
END:VCALENDAR
"""


def _free_busy(data: str) -> FreeBusy:
    """Return a free/busy answer of the server."""
    return FreeBusy(Mock(), data)


BUSY_PERIODS = [
    {"start": "2026-11-29T01:00:00-08:00", "end": "2026-11-29T02:00:00-08:00"},
    {"start": "2026-11-29T09:00:00-08:00", "end": "2026-11-29T11:00:00-08:00"},
    {"start": "2026-11-29T12:00:00-08:00", "end": "2026-11-29T12:30:00-08:00"},
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up config entry platforms."""
    return [Platform.CALENDAR]


@pytest.fixture(name="calendar")
def mock_calendar() -> Mock:
    """Fixture for the calendar of the account."""
    calendar = Mock()
    calendar.url = URL("https://example.com/example/")
    calendar.search.return_value = []
    calendar.get_display_name.return_value = "Example"
    calendar.get_supported_components.return_value = ["VEVENT"]
    calendar.get_property.return_value = None
    return calendar


@pytest.fixture(name="calendars")
def mock_calendars(calendar: Mock) -> list[Mock]:
    """Fixture to provide calendars returned by CalDAV client."""
    return [calendar]


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture to set up the config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)


async def _get_free_busy(hass: HomeAssistant, **data: Any) -> Any:
    """Call the action for the calendar."""
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FREE_BUSY,
        {ATTR_ENTITY_ID: TEST_ENTITY, "start": START, "end": END, **data},
        blocking=True,
        return_response=True,
    )


async def test_get_free_busy_registered_without_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the action exists when no config entry is loaded."""
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert await async_setup_component(hass, DOMAIN, {})

    assert hass.services.has_service(DOMAIN, SERVICE_GET_FREE_BUSY)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(FREE_BUSY_LINES, BUSY_PERIODS, id="freebusy_lines"),
        pytest.param(
            FREE_BUSY_COMPONENTS, BUSY_PERIODS, id="component_per_period_as_radicale"
        ),
        pytest.param(
            FREE_BUSY_SINGLE,
            [
                {
                    "start": "2026-11-29T09:00:00-08:00",
                    "end": "2026-11-29T10:00:00-08:00",
                }
            ],
            id="single_freebusy_line",
        ),
        pytest.param(
            FREE_BUSY_TOUCHING_CONTAINED,
            [
                {
                    "start": "2026-11-29T09:00:00-08:00",
                    "end": "2026-11-29T12:30:00-08:00",
                }
            ],
            id="touching_and_contained_as_radicale",
        ),
        pytest.param(
            FREE_BUSY_BEYOND_RANGE,
            [
                {
                    "start": "2026-11-29T00:00:00-08:00",
                    "end": "2026-11-29T01:00:00-08:00",
                },
                {
                    "start": "2026-11-29T23:00:00-08:00",
                    "end": "2026-11-30T00:00:00-08:00",
                },
            ],
            id="cut_to_range_as_radicale",
        ),
        pytest.param(FREE_BUSY_ZERO_LENGTH, [], id="event_without_length"),
        pytest.param(FREE_BUSY_NOTHING, [], id="nothing_busy"),
        pytest.param(FREE_BUSY_NO_COMPONENT, [], id="nothing_busy_as_radicale"),
    ],
)
async def test_get_free_busy_returns_merged_busy_periods_in_local_time(
    hass: HomeAssistant,
    calendar: Mock,
    data: str,
    expected: list[dict[str, str]],
) -> None:
    """Test the busy periods of a calendar within the range, without the free ones."""
    calendar.freebusy_request.return_value = _free_busy(data)

    response = await _get_free_busy(hass)

    assert response == {TEST_ENTITY: {"periods": expected}}
    calendar.freebusy_request.assert_called_once_with(
        datetime(2026, 11, 29, 8, tzinfo=UTC), datetime(2026, 11, 30, 8, tzinfo=UTC)
    )


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(
            ReportError(status=501),
            "free_busy_query_not_supported",
            id="report_not_implemented_as_sogo",
        ),
        pytest.param(
            ReportError(status=405),
            "free_busy_query_not_supported",
            id="report_not_allowed",
        ),
        pytest.param(
            ReportError(status=500), "free_busy_request_failed", id="report_failed"
        ),
        pytest.param(DAVError(), "free_busy_request_failed", id="dav_error"),
        pytest.param(
            caldav_requests.exceptions.ConnectionError(),
            "free_busy_request_failed",
            id="connection_error",
        ),
        pytest.param(
            caldav_requests.exceptions.Timeout(),
            "free_busy_request_failed",
            id="timeout",
        ),
    ],
)
async def test_get_free_busy_fails_when_the_calendar_query_fails(
    hass: HomeAssistant, calendar: Mock, error: Exception, translation_key: str
) -> None:
    """Test a failed free/busy query on the calendar is an error."""
    calendar.freebusy_request.side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        await _get_free_busy(hass)

    assert type(err.value) is HomeAssistantError
    assert err.value.translation_key == translation_key
    assert err.value.translation_placeholders == {"calendar": TEST_ENTITY}
    assert err.value.__cause__ is error


@pytest.mark.parametrize("end", [START, "2026-11-28 00:00:00"], ids=["same", "before"])
async def test_get_free_busy_fails_when_end_is_not_after_start(
    hass: HomeAssistant, calendar: Mock, end: str
) -> None:
    """Test a time range that does not end after its start is refused."""
    with pytest.raises(ServiceValidationError) as err:
        await _get_free_busy(hass, end=end)

    assert err.value.translation_key == "end_not_after_start"
    calendar.freebusy_request.assert_not_called()


@pytest.mark.parametrize(
    ("data", "return_response", "error"),
    [
        ({"end": END}, True, probatio.Invalid),
        ({"start": START}, True, probatio.Invalid),
        ({"start": START, "end": END}, False, ServiceValidationError),
    ],
    ids=["without_start", "without_end", "without_response"],
)
async def test_get_free_busy_needs_a_range_and_a_response(
    hass: HomeAssistant,
    calendar: Mock,
    data: dict[str, str],
    return_response: bool,
    error: type[Exception],
) -> None:
    """Test the action is refused without a start, an end or a response."""
    with pytest.raises(error):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FREE_BUSY,
            {ATTR_ENTITY_ID: TEST_ENTITY, **data},
            blocking=True,
            return_response=return_response,
        )

    calendar.freebusy_request.assert_not_called()
