"""Tests for init module."""

from datetime import timedelta
import http
import time
from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import (
    ApiException,
    AuthException,
    HusqvarnaWSServerHandshakeError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.components.husqvarna_automower.coordinator import (
    MAX_WS_RECONNECT_TIME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed
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
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.DEFAULT_RECONNECT_TIME",
        new=0,
    ):
        mock_automower_client.auth.websocket_connect.side_effect = (
            HusqvarnaWSServerHandshakeError("Boom")
        )
        await setup_integration(hass, mock_config_entry)
        assert (
            "Failed to connect to websocket. Trying to reconnect: Boom" in caplog.text
        )
        # await hass.async_block_till_done()
        # assert mock_automower_client.auth.websocket_connect.call_count == 1
        # assert mock_config_entry.state is ConfigEntryState.LOADED

        # reconnect_time = 0  # Default to zero for testing
        test_range = 1940
        start_call_count = mock_automower_client.auth.websocket_connect.call_count
        for count in range(1, test_range):
            # reconnect_time = min(reconnect_time * 2, MAX_WS_RECONNECT_TIME)
            # freezer.tick(timedelta(seconds=reconnect_time))
            # async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (
                mock_automower_client.auth.websocket_connect.call_count
                == start_call_count + count
            )
            assert mock_config_entry.state is ConfigEntryState.LOADED

        # Simulate a successful connection and starting of listening
        mock_automower_client.auth.websocket_connect.side_effect = None
        freezer.tick(timedelta(seconds=MAX_WS_RECONNECT_TIME))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_automower_client.start_listening.call_count == 1

        # Test that reconnection occurs if the websocket disconnects again
        mock_automower_client.auth.websocket_connect.side_effect = (
            HusqvarnaWSServerHandshakeError("Boom")
        )
        freezer.tick(timedelta(seconds=0))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            mock_automower_client.auth.websocket_connect.call_count
            == start_call_count + test_range + 1
        )


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
