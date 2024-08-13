"""Tests for init module."""

import http
import time
from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import (
    ApiException,
    AuthException,
    HusqvarnaWSServerHandshakeError,
    TimeoutException,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("scope"),
    [
        ("iam:read"),
    ],
)
async def test_load_missing_scope(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the entry starts a reauth with the missing token scope."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "missing_scope"


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
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


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (ApiException, ConfigEntryState.SETUP_RETRY),
        (AuthException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test update failed."""
    mock_automower_client.get_status.side_effect = exception("Test error")
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is entry_state


async def test_websocket_not_available(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test trying to reload the websocket."""
    # Patch DEFAULT_RECONNECT_TIME to 0 for the test
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.DEFAULT_RECONNECT_TIME",
        new=0,
    ):
        # Simulate a WebSocket handshake error
        mock_automower_client.auth.websocket_connect.side_effect = (
            HusqvarnaWSServerHandshakeError("Boom")
        )

        # Setup integration and verify initial log error message
        await setup_integration(hass, mock_config_entry)
        assert (
            "Failed to connect to websocket. Trying to reconnect: Boom" in caplog.text
        )
        # Simulate a successful connection
        mock_automower_client.auth.websocket_connect.side_effect = None
        caplog.clear()
        mock_automower_client.reset_mock()
        await hass.async_block_till_done()
        assert mock_automower_client.auth.websocket_connect.call_count == 1
        assert mock_automower_client.start_listening.call_count == 1
        assert "Trying to reconnect: Boom" not in caplog.text

        # Simulate a start_listening TimeoutException
        mock_automower_client.start_listening.side_effect = TimeoutException("Boom")
        await hass.async_block_till_done()
        assert mock_automower_client.auth.websocket_connect.call_count == 2
        assert mock_automower_client.start_listening.call_count == 2

        # Simulate a successful connection
        caplog.clear()
        mock_automower_client.start_listening.side_effect = None
        await hass.async_block_till_done()
        assert mock_automower_client.auth.websocket_connect.call_count == 3
        assert mock_automower_client.start_listening.call_count == 3
        assert "Trying to reconnect: Boom" not in caplog.text

        # Simulate hass shutting down
        mock_automower_client.reset_mock()
        await hass.async_stop()
        assert mock_automower_client.auth.websocket_connect.call_count == 0
        assert mock_automower_client.start_listening.call_count == 0


async def test_device_info(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select platform."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_MOWER_ID)},
    )
    assert reg_device == snapshot
