"""Configure tests for the Twitch integration."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

import pytest
from twitchAPI.object.api import FollowedChannel, Stream, TwitchUser, UserSubscription

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.twitch.const import DOMAIN, OAUTH2_TOKEN, OAUTH_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TwitchIterObject, get_generator

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
TITLE = "Test"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
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


@pytest.fixture
def twitch_mock() -> Generator[AsyncMock]:
    """Return as fixture to inject other mocks."""
    with (
        patch(
            "homeassistant.components.twitch.Twitch",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.twitch.config_flow.Twitch",
            new=mock_client,
        ),
    ):
        mock_client.return_value.get_users = lambda *args, **kwargs: get_generator(
            "get_users.json", TwitchUser
        )
        mock_client.return_value.get_followed_channels.return_value = TwitchIterObject(
            "get_followed_channels.json", FollowedChannel
        )
        mock_client.return_value.get_streams.return_value = get_generator(
            "get_streams.json", Stream
        )
        mock_client.return_value.check_user_subscription.return_value = (
            UserSubscription(
                **load_json_object_fixture("check_user_subscription.json", DOMAIN)
            )
        )
        mock_client.return_value.has_required_auth.return_value = True
        yield mock_client
