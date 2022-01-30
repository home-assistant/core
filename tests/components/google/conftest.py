"""Test configuration and mocks for the google integration."""
from collections.abc import Callable
from typing import Any, Generator, TypeVar
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.google import GoogleCalendarService

ApiResult = Callable[[dict[str, Any]], None]
T = TypeVar("T")
YieldFixture = Generator[T, None, None]


CALENDAR_ID = "qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com"
TEST_CALENDAR = {
    "id": CALENDAR_ID,
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


@pytest.fixture
def mock_events_list(
    google_service: GoogleCalendarService,
) -> Callable[[dict[str, Any]], None]:
    """Fixture to construct a fake event list API response."""

    def _put_result(response: dict[str, Any]) -> None:
        google_service.return_value.get.return_value.events.return_value.list.return_value.execute.return_value = (
            response
        )
        return

    return _put_result


@pytest.fixture
def mock_calendars_list(
    google_service: GoogleCalendarService,
) -> ApiResult:
    """Fixture to construct a fake calendar list API response."""

    def _put_result(response: dict[str, Any]) -> None:
        google_service.return_value.get.return_value.calendarList.return_value.list.return_value.execute.return_value = (
            response
        )
        return

    return _put_result


@pytest.fixture
def mock_insert_event(
    google_service: GoogleCalendarService,
) -> Mock:
    """Fixture to create a mock to capture new events added to the API."""
    insert_mock = Mock()
    google_service.return_value.get.return_value.events.return_value.insert = (
        insert_mock
    )
    return insert_mock
