"""Tests for the Level Lock integration init/unload."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
import time

import pytest

from homeassistant.components.levelhome.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import OAUTH2_TOKEN, SERVER_ACCESS_TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
) -> None:
    """Test setting up and unloading a config entry."""
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    # Unload
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed during setup."""
    # Mock the token refresh endpoint
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )

    # Verify initial token
    assert config_entry.data["token"]["access_token"] == "test-access-token"
    assert config_entry.data["token"]["refresh_token"] == "test-refresh-token"

    # Setup integration - should trigger token refresh
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    # Verify token was refreshed
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert (
        entries[0].data["token"]["access_token"] == SERVER_ACCESS_TOKEN["access_token"]
    )
    assert (
        entries[0].data["token"]["refresh_token"]
        == SERVER_ACCESS_TOKEN["refresh_token"]
    )
    assert entries[0].data["token"]["expires_in"] == SERVER_ACCESS_TOKEN["expires_in"]


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.BAD_REQUEST,
    ],
    ids=["unauthorized", "bad_request"],
)
async def test_expired_token_refresh_failure_auth_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
) -> None:
    """Test failed token refresh due to auth errors results in setup retry."""
    # Mock token refresh failure with auth error
    aioclient_mock.post(OAUTH2_TOKEN, status=status)

    # Setup should fail - currently results in SETUP_RETRY
    # (Level Lock integration doesn't yet catch ConfigEntryAuthFailed specifically)
    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
    ],
    ids=["internal_server_error", "forbidden", "not_found"],
)
async def test_expired_token_refresh_transient_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
) -> None:
    """Test transient refresh failures result in setup retry."""
    # Mock transient failure
    aioclient_mock.post(OAUTH2_TOKEN, status=status)

    # Setup should fail with retry state
    assert not await integration_setup()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("expires_at", [time.time() + 3600], ids=["valid"])
async def test_valid_token_no_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test valid token does not trigger refresh."""
    # Setup integration with valid token
    assert await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    # Verify no token refresh calls were made
    assert not any(
        call[0] == "POST" and OAUTH2_TOKEN in str(call[1])
        for call in aioclient_mock.mock_calls
    )

    # Verify token unchanged
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data["token"]["access_token"] == "test-access-token"
    assert entries[0].data["token"]["refresh_token"] == "test-refresh-token"
