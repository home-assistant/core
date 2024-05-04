"""Configure tests for the Twitch integration."""

from collections.abc import Awaitable, Callable, Generator
import time
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.twitch.const import DOMAIN, OAUTH2_TOKEN, OAUTH_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.twitch import TwitchMock
from tests.test_util.aiohttp import AiohttpClientMocker

ComponentSetup = Callable[[TwitchMock | None], Awaitable[None]]

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
TITLE = "Test"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.twitch.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return [scope.value for scope in OAUTH_SCOPES]


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Twitch entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id="123",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
        options={"channels": ["internetofthings"]},
    )


@pytest.fixture(autouse=True)
def mock_connection(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock Twitch connection."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )


@pytest.fixture(name="twitch_mock")
def twitch_mock() -> TwitchMock:
    """Return as fixture to inject other mocks."""
    return TwitchMock()


@pytest.fixture(name="twitch")
def mock_twitch(twitch_mock: TwitchMock):
    """Mock Twitch."""
    with (
        patch(
            "homeassistant.components.twitch.Twitch",
            return_value=twitch_mock,
        ),
        patch(
            "homeassistant.components.twitch.config_flow.Twitch",
            return_value=twitch_mock,
        ),
    ):
        yield twitch_mock
