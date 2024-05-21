"""Test configuration and mocks for the google integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
import datetime
import http
import time
from typing import Any
from unittest.mock import Mock, mock_open, patch

from aiohttp.client_exceptions import ClientError
from gcal_sync.auth import API_BASE_URL
from oauth2client.client import OAuth2Credentials
import pytest
import yaml

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

type ApiResult = Callable[[dict[str, Any]], None]
type ComponentSetup = Callable[[], Awaitable[bool]]
type AsyncYieldFixture[_T] = AsyncGenerator[_T, None]


CALENDAR_ID = "qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com"
EMAIL_ADDRESS = "user@gmail.com"

# Entities can either be created based on data directly from the API, or from
# the yaml config that overrides the entity name and other settings. A test
# can use a fixture to exercise either case.
TEST_API_ENTITY = "calendar.we_are_we_are_a_test_calendar"
TEST_API_ENTITY_NAME = "We are, we are, a... test calendar"
# Name of the entity when using yaml configuration overrides
TEST_YAML_ENTITY = "calendar.backyard_light"
TEST_YAML_ENTITY_NAME = "Backyard light"

# A calendar object returned from the API
TEST_API_CALENDAR = {
    "id": CALENDAR_ID,
    "etag": '"3584134138943410"',
    "timeZone": "UTC",
    "foregroundColor": "#000000",
    "selected": True,
    "kind": "calendar#calendarListEntry",
    "backgroundColor": "#16a765",
    "description": "Test Calendar",
    "summary": "We are, we are, a... Test Calendar",
    "colorId": "8",
    "defaultReminders": [],
}

TEST_EVENT = {
    "summary": "Test All Day Event",
    "start": {},
    "end": {},
    "location": "Test Cases",
    "description": "test event",
    "kind": "calendar#event",
    "created": "2016-06-23T16:37:57.000Z",
    "transparency": "transparent",
    "updated": "2016-06-24T01:57:21.045Z",
    "reminders": {"useDefault": True},
    "organizer": {
        "email": "uvrttabwegnui4gtia3vyqb@import.calendar.google.com",
        "displayName": "Organizer Name",
        "self": True,
    },
    "sequence": 0,
    "creator": {
        "email": "uvrttabwegnui4gtia3vyqb@import.calendar.google.com",
        "displayName": "Organizer Name",
        "self": True,
    },
    "id": "_c8rinwq863h45qnucyoi43ny8",
    "etag": '"2933466882090000"',
    "htmlLink": "https://www.google.com/calendar/event?eid=*******",
    "iCalUID": "cydrevtfuybguinhomj@google.com",
    "status": "confirmed",
}

CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret"


@pytest.fixture(name="calendar_access_role")
def test_calendar_access_role() -> str:
    """Default access role to use for test_api_calendar in tests."""
    return "owner"


@pytest.fixture
def test_api_calendar(calendar_access_role: str) -> None:
    """Return a test calendar object used in API responses."""
    return {
        **TEST_API_CALENDAR,
        "accessRole": calendar_access_role,
    }


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
def mock_calendars_yaml(
    hass: HomeAssistant,
    calendars_config: list[dict[str, Any]],
) -> Generator[Mock, None, None]:
    """Fixture that prepares the google_calendars.yaml mocks."""
    mocked_open_function = mock_open(
        read_data=yaml.dump(calendars_config) if calendars_config else None
    )
    with patch("homeassistant.components.google.open", mocked_open_function):
        yield mocked_open_function


@pytest.fixture
def token_scopes() -> list[str]:
    """Fixture for scopes used during test."""
    return ["https://www.googleapis.com/auth/calendar"]


@pytest.fixture
def token_expiry() -> datetime.datetime:
    """Expiration time for credentials used in the test."""
    # OAuth library returns an offset-naive timestamp
    return dt_util.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=1)


@pytest.fixture
def creds(
    token_scopes: list[str], token_expiry: datetime.datetime
) -> OAuth2Credentials:
    """Fixture that defines creds used in the test."""
    return OAuth2Credentials(
        access_token="ACCESS_TOKEN",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        refresh_token="REFRESH_TOKEN",
        token_expiry=token_expiry,
        token_uri="http://example.com",
        user_agent="n/a",
        scopes=token_scopes,
    )


@pytest.fixture
def config_entry_token_expiry() -> float:
    """Fixture for token expiration value stored in the config entry."""
    return time.time() + 86400


@pytest.fixture
def config_entry_options() -> dict[str, Any] | None:
    """Fixture to set initial config entry options."""
    return None


@pytest.fixture
def config_entry_unique_id() -> str:
    """Fixture that returns the default config entry unique id."""
    return EMAIL_ADDRESS


@pytest.fixture
def config_entry(
    config_entry_unique_id: str,
    token_scopes: list[str],
    config_entry_token_expiry: float,
    config_entry_options: dict[str, Any] | None,
) -> MockConfigEntry:
    """Fixture to create a config entry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=config_entry_unique_id,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "ACCESS_TOKEN",
                "refresh_token": "REFRESH_TOKEN",
                "scope": " ".join(token_scopes),
                "token_type": "Bearer",
                "expires_at": config_entry_token_expiry,
            },
        },
        options=config_entry_options,
    )


@pytest.fixture
def mock_events_list(
    aioclient_mock: AiohttpClientMocker,
) -> ApiResult:
    """Fixture to construct a fake event list API response."""

    def _put_result(
        response: dict[str, Any],
        calendar_id: str | None = None,
        exc: ClientError | None = None,
    ) -> None:
        if calendar_id is None:
            calendar_id = CALENDAR_ID
        resp = {
            **response,
            "nextSyncToken": "sync-token",
        }
        aioclient_mock.get(
            f"{API_BASE_URL}/calendars/{calendar_id}/events",
            json=resp,
            exc=exc,
        )

    return _put_result


@pytest.fixture
def mock_events_list_items(
    mock_events_list: Callable[[dict[str, Any]], None],
) -> Callable[[list[dict[str, Any]]], None]:
    """Fixture to construct an API response containing event items."""

    def _put_items(items: list[dict[str, Any]]) -> None:
        mock_events_list({"items": items})

    return _put_items


@pytest.fixture
def mock_calendars_list(
    aioclient_mock: AiohttpClientMocker,
) -> ApiResult:
    """Fixture to construct a fake calendar list API response."""

    def _result(response: dict[str, Any], exc: ClientError | None = None) -> None:
        resp = {
            **response,
            "nextSyncToken": "sync-token",
        }
        aioclient_mock.get(
            f"{API_BASE_URL}/users/me/calendarList",
            json=resp,
            exc=exc,
        )

    return _result


@pytest.fixture
def mock_calendar_get(
    aioclient_mock: AiohttpClientMocker,
) -> Callable[[...], None]:
    """Fixture for returning a calendar get response."""

    def _result(
        calendar_id: str,
        response: dict[str, Any],
        exc: ClientError | None = None,
        status: http.HTTPStatus = http.HTTPStatus.OK,
    ) -> None:
        aioclient_mock.get(
            f"{API_BASE_URL}/calendars/{calendar_id}",
            json=response,
            exc=exc,
            status=status,
        )

    return _result


@pytest.fixture
def mock_insert_event(
    aioclient_mock: AiohttpClientMocker,
) -> Callable[[...], None]:
    """Fixture for capturing event creation."""

    def _expect_result(
        calendar_id: str = CALENDAR_ID, exc: ClientError | None = None
    ) -> None:
        aioclient_mock.post(
            f"{API_BASE_URL}/calendars/{calendar_id}/events",
            exc=exc,
        )

    return _expect_result


@pytest.fixture(autouse=True)
async def set_time_zone(hass):
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    await hass.config.async_set_time_zone("America/Regina")


@pytest.fixture
def component_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> ComponentSetup:
    """Fixture for setting up the integration."""

    async def _setup_func() -> bool:
        assert await async_setup_component(hass, "application_credentials", {})
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential("client-id", "client-secret"),
        )
        config_entry.add_to_hass(hass)
        return await hass.config_entries.async_setup(config_entry.entry_id)

    return _setup_func
