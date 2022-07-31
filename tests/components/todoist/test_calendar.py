"""Unit tests for the Todoist calendar platform."""
from datetime import datetime

from homeassistant.components.todoist.calendar import _parse_due_date
from homeassistant.components.todoist.types import DueDate
from homeassistant.util import dt


def test_parse_due_date_invalid():
    """Test None is returned if the due date can't be parsed."""
    data: DueDate = {
        "date": "invalid",
        "is_recurring": False,
        "lang": "en",
        "string": "",
        "timezone": None,
    }
    assert _parse_due_date(data, timezone_offset=-8) is None


def test_parse_due_date_with_no_time_data():
    """Test due date is parsed correctly when it has no time data."""
    data: DueDate = {
        "date": "2022-02-02",
        "is_recurring": False,
        "lang": "en",
        "string": "Feb 2 2:00 PM",
        "timezone": None,
    }
    actual = _parse_due_date(data, timezone_offset=-8)
    assert datetime(2022, 2, 2, 8, 0, 0, tzinfo=dt.UTC) == actual


def test_parse_due_date_without_timezone_uses_offset():
    """Test due date uses user local timezone offset when it has no timezone."""
    data: DueDate = {
        "date": "2022-02-02T14:00:00",
        "is_recurring": False,
        "lang": "en",
        "string": "Feb 2 2:00 PM",
        "timezone": None,
    }
    actual = _parse_due_date(data, timezone_offset=-8)
    assert datetime(2022, 2, 2, 22, 0, 0, tzinfo=dt.UTC) == actual
