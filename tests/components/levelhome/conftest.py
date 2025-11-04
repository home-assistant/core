"""Configure tests for the Level Lock integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.levelhome.const import (
    CONF_OAUTH2_BASE_URL,
    CONF_PARTNER_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
    OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH,
    OAUTH2_OTP_CONFIRM_PATH,
    OAUTH2_TOKEN_EXCHANGE_PATH,
    PARTNER_OTP_START_PATH,
)
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
FAKE_ACCESS_TOKEN = "test-access-token"
FAKE_REFRESH_TOKEN = "test-refresh-token"
FAKE_AUTH_IMPL = DOMAIN
OAUTH2_TOKEN = f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}"

# Server response for refresh token - differs from config entry token
SERVER_ACCESS_TOKEN = {
    "access_token": "updated-access-token",
    "refresh_token": "updated-refresh-token",
    "token_type": "Bearer",
    "expires_in": 3600,
}


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 3600


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "expires_in": 3600,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Level Lock",
        unique_id="test-unique-id",
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        options={
            CONF_OAUTH2_BASE_URL: DEFAULT_OAUTH2_BASE_URL,
            CONF_PARTNER_BASE_URL: DEFAULT_PARTNER_BASE_URL,
        },
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        FAKE_AUTH_IMPL,
    )


@pytest.fixture(name="mock_levelhome_api")
def mock_levelhome_api(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Level Lock API endpoints."""
    # Mock the locks endpoint that coordinator calls during first refresh
    aioclient_mock.get(
        "https://sidewalk-dev.level.co/v1/locks",
        json={"locks": []},  # Empty list of locks wrapped in object
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


@pytest.fixture(name="mock_websocket_manager")
def mock_websocket_manager() -> Generator[AsyncMock]:
    """Mock the Level Lock WebSocket manager."""
    with patch(
        "homeassistant.components.levelhome._lib.level_ha.WebsocketManager",
        autospec=True,
    ) as mock_ws:
        ws = mock_ws.return_value
        ws.async_start = AsyncMock(return_value=None)
        ws.async_stop = AsyncMock(return_value=None)
        yield mock_ws


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_levelhome_api: None,
    mock_websocket_manager: AsyncMock,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return result

    return run


@pytest.fixture(name="fake_oauth_impl")
def mock_fake_oauth_impl() -> SimpleNamespace:
    """Fixture for a fake OAuth2 implementation."""
    return SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="test-client-id",
        redirect_uri="https://example.com/redirect",
        extra_token_resolve_data={},
    )


@pytest.fixture(name="mock_oauth_patches")
def mock_oauth_patches(fake_oauth_impl: SimpleNamespace) -> Generator[None]:
    """Fixture to patch OAuth2 flow handlers."""
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_oauth_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        yield


@pytest.fixture(name="mock_oauth_responses")
def mock_oauth_responses(aioclient_mock: AiohttpClientMocker) -> None:
    """Fixture to mock successful OAuth2 and OTP responses."""
    # Mock authorize HTML returning request_uuid
    aioclient_mock.get(
        "https://oauth.example/authorize",
        text='<html><input type="hidden" name="request_uuid" value="req-123"></html>',
    )

    # OTP start on partner server
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
    )

    # OTP confirm
    aioclient_mock.post(
        f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
    )

    # Grant accept returning redirect_uri with code
    aioclient_mock.post(
        f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
        json={"redirect_uri": "https://example.com/redirect?code=authcode-xyz"},
        status=200,
    )

    # Token exchange
    aioclient_mock.post(
        f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
        json={
            "access_token": "at",
            "refresh_token": "rt",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
        status=200,
    )
