"""Configure tests for the Level Lock integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.levelhome.const import (
    CONF_PARTNER_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
    OAUTH2_TOKEN_EXCHANGE_PATH,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
FAKE_ACCESS_TOKEN = "test-access-token"
FAKE_REFRESH_TOKEN = "test-refresh-token"
FAKE_AUTH_IMPL = DOMAIN

OAUTH2_TOKEN_REFRESH = f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}"
SERVER_ACCESS_TOKEN = {
    "access_token": "refreshed-access-token",
    "refresh_token": "refreshed-refresh-token",
    "token_type": "Bearer",
    "expires_in": 3600,
}


@pytest.fixture
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
            CONF_PARTNER_BASE_URL: DEFAULT_PARTNER_BASE_URL,
        },
    )


@pytest.fixture(name="mock_levelhome_api")
def mock_levelhome_api() -> None:
    """Mock the Level Lock API endpoints (WebSocket only, no HTTP)."""


@pytest.fixture(name="mock_websocket_manager")
def mock_websocket_manager() -> Generator[AsyncMock]:
    """Mock the Level Lock WebSocket manager."""
    with patch("level_ws_client.WebsocketManager", autospec=True) as mock_ws:
        ws = mock_ws.return_value
        ws.async_start = AsyncMock(return_value=None)
        ws.async_stop = AsyncMock(return_value=None)
        ws.async_get_devices = AsyncMock(return_value=[])
        ws.async_get_device_state = AsyncMock(return_value=None)
        ws.register_device_uuid = lambda lock_id, uuid: None
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
