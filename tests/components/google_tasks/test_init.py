"""Tests for Google Tasks."""
from collections.abc import Awaitable, Callable
import http
import time

import pytest

from homeassistant.components.google_tasks import DOMAIN
from homeassistant.components.google_tasks.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Test successful setup and unload."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert not hass.services.async_services().get(DOMAIN)


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await integration_setup()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data["token"]["access_token"] == "updated-access-token"
    assert config_entry.data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_RETRY,  # Will trigger reauth in the future
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    setup_credentials: None,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await integration_setup()

    assert config_entry.state is expected_state
