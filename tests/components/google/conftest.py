"""Test configuration and mocks for the google integration."""
from unittest.mock import patch

import pytest

TEST_CALENDAR = {
    "id": "qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com",
    "etag": '"3584134138943410"',
    "timeZone": "UTC",
    "accessRole": "reader",
    "foregroundColor": "#000000",
    "selected": True,
    "kind": "calendar#calendarListEntry",
    "backgroundColor": "#16a765",
    "description": "Test Calendar",
    "summary": "We are, we are, a... Test Calendar",
    "colorId": "8",
    "defaultReminders": [],
    "track": True,
}


@pytest.fixture
def test_calendar():
    """Return a test calendar."""
    return TEST_CALENDAR


@pytest.fixture
def mock_next_event():
    """Mock the google calendar data."""
    patch_google_cal = patch(
        "homeassistant.components.google.calendar.GoogleCalendarData"
    )
    with patch_google_cal as google_cal_data:
        yield google_cal_data
