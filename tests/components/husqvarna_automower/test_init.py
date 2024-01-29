"""Tests for init module."""
import http
import time
from unittest.mock import patch

from aiohttp import ClientError
import pytest

from homeassistant.components.husqvarna_automower.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .common import setup_platform

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

SCAN_INTERVAL = dt_util.dt.timedelta(60)
TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


async def test_async_setup_raises_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry,
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


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


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

    await setup_platform(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
