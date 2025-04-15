"""Configure tests for the YouTube integration."""

from collections.abc import Awaitable, Callable, Coroutine
import time
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.youtube.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockYouTube

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

type ComponentSetup = Callable[[], Awaitable[MockYouTube]]

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
]
TITLE = "Google for Developers"
TOKEN = "homeassistant.components.youtube.api.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid"


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


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
    """Create YouTube entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
        options={"channels": ["UC_x5XG1OV2P6uZZ5FSM9Ttw"]},
    )


@pytest.fixture(autouse=True)
def mock_connection(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock YouTube connection."""
    aioclient_mock.post(
        GOOGLE_TOKEN_URI,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Coroutine[Any, Any, MockYouTube]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )

    async def func() -> MockYouTube:
        mock = MockYouTube()
        with patch("homeassistant.components.youtube.api.YouTube", return_value=mock):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        return mock

    return func
