"""Test configuration and mocks for the google integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
from typing import Any, Generator, TypeVar
from unittest.mock import Mock, mock_open, patch

from googleapiclient import discovery as google_discovery
from oauth2client.client import Credentials, OAuth2Credentials
import pytest
import yaml

from homeassistant.components.google import CONF_TRACK_NEW, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.dt import utcnow

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE

ApiResult = Callable[[dict[str, Any]], None]
ComponentSetup = Callable[[], Awaitable[bool]]
T = TypeVar("T")
YieldFixture = Generator[T, None, None]


CALENDAR_ID = "qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com"

# Entities can either be created based on data directly from the API, or from
# the yaml config that overrides the entity name and other settings. A test
# can use a fixture to exercise either case.
TEST_API_ENTITY = "calendar.we_are_we_are_a_test_calendar"
TEST_API_ENTITY_NAME = "We are, we are, a... Test Calendar"
# Name of the entity when using yaml configuration overrides
TEST_YAML_ENTITY = "calendar.backyard_light"
TEST_YAML_ENTITY_NAME = "Backyard Light"

# A calendar object returned from the API
TEST_API_CALENDAR = {
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
}


@pytest.fixture
def test_api_calendar():
    """Return a test calendar object used in API responses."""
    return TEST_API_CALENDAR


@pytest.fixture
def calendars_config_track() -> bool:
    """Fixture that determines the 'track' setting in yaml config."""
    return True


@pytest.fixture
def calendars_config_ignore_availability() -> bool:
    """Fixture that determines the 'ignore_availability' setting in yaml config."""
    return None


@pytest.fixture
def calendars_config_entity(
    calendars_config_track: bool, calendars_config_ignore_availability: bool | None
) -> dict[str, Any]:
    """Fixture that creates an entity within the yaml configuration."""
    entity = {
        "device_id": "backyard_light",
        "name": "Backyard Light",
        "search": "#Backyard",
        "track": calendars_config_track,
    }
    if calendars_config_ignore_availability is not None:
        entity["ignore_availability"] = calendars_config_ignore_availability
    return entity


@pytest.fixture
def calendars_config(calendars_config_entity: dict[str, Any]) -> list[dict[str, Any]]:
    """Fixture that specifies the calendar yaml configuration."""
    return [
        {
            "cal_id": CALENDAR_ID,
            "entities": [calendars_config_entity],
        }
    ]


@pytest.fixture
async def mock_calendars_yaml(
    hass: HomeAssistant,
    calendars_config: list[dict[str, Any]],
) -> None:
    """Fixture that prepares the google_calendars.yaml mocks."""
    mocked_open_function = mock_open(read_data=yaml.dump(calendars_config))
    with patch("homeassistant.components.google.open", mocked_open_function):
        yield


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
def mock_events_list_items(
    mock_events_list: Callable[[dict[str, Any]], None]
) -> Callable[list[[dict[str, Any]]], None]:
    """Fixture to construct an API response containing event items."""

    def _put_items(items: list[dict[str, Any]]) -> None:
        mock_events_list({"items": items})
        return

    return _put_items


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


@pytest.fixture(autouse=True)
def set_time_zone(hass):
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    hass.config.time_zone = "CST"
    dt_util.set_default_time_zone(dt_util.get_time_zone("America/Regina"))
    yield
    dt_util.set_default_time_zone(ORIG_TIMEZONE)


@pytest.fixture
def google_config_track_new() -> None:
    """Fixture for tests to set the 'track_new' configuration.yaml setting."""
    return None


@pytest.fixture
def google_config(google_config_track_new: bool | None) -> dict[str, Any]:
    """Fixture for overriding component config."""
    google_config = {CONF_CLIENT_ID: "client-id", CONF_CLIENT_SECRET: "client-secret"}
    if google_config_track_new is not None:
        google_config[CONF_TRACK_NEW] = google_config_track_new
    return google_config


@pytest.fixture
async def config(google_config: dict[str, Any]) -> dict[str, Any]:
    """Fixture for overriding component config."""
    return {DOMAIN: google_config}


@pytest.fixture
async def component_setup(
    hass: HomeAssistant, config: dict[str, Any]
) -> ComponentSetup:
    """Fixture for setting up the integration."""

    async def _setup_func() -> bool:
        result = await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        return result

    return _setup_func
