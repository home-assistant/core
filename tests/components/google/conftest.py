"""Test configuration and mocks for the google integration."""
from __future__ import annotations

from collections.abc import Callable
import datetime
from typing import Any, Generator, TypeVar
from unittest.mock import Mock, patch

from googleapiclient import discovery as google_discovery
from oauth2client.client import Credentials, OAuth2Credentials
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

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


class FakeStorage:
    """A fake storage object for persiting creds."""

    def __init__(self) -> None:
        """Initialize FakeStorage."""
        self._creds: Credentials | None = None

    def get(self) -> Credentials | None:
        """Get credentials from storage."""
        return self._creds

    def put(self, creds: Credentials) -> None:
        """Put credentials in storage."""
        self._creds = creds


@pytest.fixture
async def token_scopes() -> list[str]:
    """Fixture for scopes used during test."""
    return ["https://www.googleapis.com/auth/calendar"]


@pytest.fixture
async def creds(token_scopes: list[str]) -> OAuth2Credentials:
    """Fixture that defines creds used in the test."""
    token_expiry = utcnow() + datetime.timedelta(days=7)
    return OAuth2Credentials(
        access_token="ACCESS_TOKEN",
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="REFRESH_TOKEN",
        token_expiry=token_expiry,
        token_uri="http://example.com",
        user_agent="n/a",
        scopes=token_scopes,
    )


@pytest.fixture(autouse=True)
async def storage() -> YieldFixture[FakeStorage]:
    """Fixture to populate an existing token file for read on startup."""
    storage = FakeStorage()
    with patch("homeassistant.components.google.Storage", return_value=storage):
        yield storage


@pytest.fixture
async def mock_token_read(
    hass: HomeAssistant,
    creds: OAuth2Credentials,
    storage: FakeStorage,
) -> None:
    """Fixture to populate an existing token file for read on startup."""
    storage.put(creds)


@pytest.fixture
def mock_next_event():
    """Mock the google calendar data."""
    patch_google_cal = patch(
        "homeassistant.components.google.calendar.GoogleCalendarData"
    )
    with patch_google_cal as google_cal_data:
        yield google_cal_data


@pytest.fixture(autouse=True)
def calendar_resource() -> YieldFixture[google_discovery.Resource]:
    """Fixture to mock out the Google discovery API."""
    with patch("homeassistant.components.google.api.google_discovery.build") as mock:
        yield mock


@pytest.fixture
def mock_events_list(
    calendar_resource: google_discovery.Resource,
) -> Callable[[dict[str, Any]], None]:
    """Fixture to construct a fake event list API response."""

    def _put_result(response: dict[str, Any]) -> None:
        calendar_resource.return_value.events.return_value.list.return_value.execute.return_value = (
            response
        )
        return

    return _put_result


@pytest.fixture
def mock_calendars_list(
    calendar_resource: google_discovery.Resource,
) -> ApiResult:
    """Fixture to construct a fake calendar list API response."""

    def _put_result(response: dict[str, Any]) -> None:
        calendar_resource.return_value.calendarList.return_value.list.return_value.execute.return_value = (
            response
        )
        return

    return _put_result


@pytest.fixture
def mock_insert_event(
    calendar_resource: google_discovery.Resource,
) -> Mock:
    """Fixture to create a mock to capture new events added to the API."""
    insert_mock = Mock()
    calendar_resource.return_value.events.return_value.insert = insert_mock
    return insert_mock
