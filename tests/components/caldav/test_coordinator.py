"""Tests for the caldav coordinator recurrence helpers."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from caldav.objects import Event
import icalendar
import pytest

from homeassistant.components.caldav.coordinator import _get_vevent, _rruleset

NEW_YORK = ZoneInfo("America/New_York")


def _vevent(ics: str) -> icalendar.cal.Component:
    """Parse the first VEVENT out of an iCalendar string."""
    return next(iter(icalendar.Calendar.from_ical(ics).walk("VEVENT")))


@pytest.mark.parametrize(
    ("ics", "expected"),
    [
        pytest.param(
            """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:1
DTSTART;TZID=America/New_York:20171225T200000
RRULE:FREQ=DAILY;UNTIL=20171227T215959
END:VEVENT
END:VCALENDAR""",
            [
                datetime(2017, 12, 25, 20, tzinfo=NEW_YORK),
                datetime(2017, 12, 26, 20, tzinfo=NEW_YORK),
                datetime(2017, 12, 27, 20, tzinfo=NEW_YORK),
            ],
            id="naive_until_uses_dtstart_timezone",
        ),
        pytest.param(
            """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20171101
RRULE:FREQ=DAILY;COUNT=3
RDATE;VALUE=DATE:20171110
EXDATE;VALUE=DATE:20171102
END:VEVENT
END:VCALENDAR""",
            [
                datetime(2017, 11, 1),
                datetime(2017, 11, 3),
                datetime(2017, 11, 10),
            ],
            id="date_valued_rdate_exdate",
        ),
        pytest.param(
            """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:3
DTSTART:20171101T100000Z
RRULE:FREQ=DAILY;COUNT=6
EXRULE:FREQ=DAILY;INTERVAL=2
END:VEVENT
END:VCALENDAR""",
            [
                datetime(2017, 11, 2, 10, tzinfo=UTC),
                datetime(2017, 11, 4, 10, tzinfo=UTC),
                datetime(2017, 11, 6, 10, tzinfo=UTC),
            ],
            id="exrule",
        ),
    ],
)
def test_rruleset(ics: str, expected: list[datetime]) -> None:
    """Test recurrence expansion of the edge cases vobject used to handle."""
    ruleset = _rruleset(_vevent(ics))
    assert ruleset is not None
    assert list(ruleset) == expected


def test_get_vevent_without_data() -> None:
    """Test a resource with no data is treated as having no VEVENT."""
    event = Event(client=None, url="0.ics", data=None, parent=None, id="0")
    assert _get_vevent(event) is None
