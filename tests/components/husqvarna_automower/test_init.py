"""Tests for init module."""
import http
import time
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

SCAN_INTERVAL = dt_util.dt.timedelta(60)


async def test_async_setup_raises_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientError("API unavailable"),
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED


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
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
