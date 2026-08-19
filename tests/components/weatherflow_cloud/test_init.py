"""Tests for weatherflow_cloud __init__ setup."""

from unittest.mock import AsyncMock, Mock

import pytest
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from websockets.protocol import State as WebSocketState

from homeassistant.components import weatherflow_cloud
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import client_context

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_rest_api")
async def test_websocket_connect_called_once(
    hass: HomeAssistant,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the shared websocket is connected exactly once during setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_websocket_api.connect.assert_awaited_once_with(client_context())


@pytest.mark.usefixtures("mock_rest_api")
async def test_stale_shared_websocket_is_replaced(
    hass: HomeAssistant,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that setup replaces the closed shared websocket after a reload."""
    weatherflow_cloud.WeatherFlowWebsocketAPI._shared_websocket = Mock(
        state=WebSocketState.CLOSED
    )

    async def _assert_stale_websocket_cleared(*args: object) -> None:
        assert weatherflow_cloud.WeatherFlowWebsocketAPI._shared_websocket is None

    mock_websocket_api.connect.side_effect = _assert_stale_websocket_cleared
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_rest_api")
async def test_entry_unload(
    hass: HomeAssistant,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unloading an entry closes the websocket."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_websocket_api.stop_all_listeners.assert_not_awaited()
    mock_websocket_api.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_rest_api")
async def test_entry_unload_with_closed_websocket(
    hass: HomeAssistant,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading an entry whose websocket is already closed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_websocket_api.close.side_effect = ConnectionClosedOK(None, None)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_websocket_api.stop_all_listeners.assert_not_awaited()
    mock_websocket_api.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_rest_api")
async def test_setup_failure_cleans_up_websocket(
    hass: HomeAssistant,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test partial setup failure stops listeners and closes the websocket."""
    mock_config_entry.add_to_hass(hass)
    mock_websocket_api.send_message.side_effect = ConnectionClosedError(None, None)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_websocket_api.stop_all_listeners.assert_not_awaited()
    mock_websocket_api.close.assert_awaited_once()


@pytest.mark.usefixtures("mock_rest_api")
async def test_websocket_connect_failure_sets_entry_not_ready(
    hass: HomeAssistant,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test websocket connection failure triggers setup retry."""
    mock_config_entry.add_to_hass(hass)
    mock_websocket_api.connect.side_effect = OSError("connect failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_websocket_api.connect.assert_awaited_once_with(client_context())
    mock_websocket_api.stop_all_listeners.assert_not_awaited()
    mock_websocket_api.close.assert_not_awaited()
