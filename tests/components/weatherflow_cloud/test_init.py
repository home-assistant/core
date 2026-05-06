"""Tests for weatherflow_cloud __init__ setup."""

from unittest.mock import AsyncMock

from websockets.exceptions import ConnectionClosedError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import client_context

from tests.common import MockConfigEntry


async def test_websocket_connect_called_once(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the shared websocket is connected exactly once during setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_websocket_api.connect.assert_awaited_once_with(client_context())


async def test_entry_unload(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
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
    mock_websocket_api.stop_all_listeners.assert_awaited_once()
    mock_websocket_api.close.assert_awaited_once()


async def test_setup_failure_cleans_up_websocket(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test partial setup failure stops listeners and closes the websocket."""
    mock_config_entry.add_to_hass(hass)
    mock_websocket_api.send_message.side_effect = ConnectionClosedError(None, None)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED
    mock_websocket_api.stop_all_listeners.assert_awaited_once()
    mock_websocket_api.close.assert_awaited_once()


async def test_websocket_connect_failure_sets_entry_error(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test websocket connection failure raises setup error."""
    mock_config_entry.add_to_hass(hass)
    mock_websocket_api.connect.side_effect = OSError("connect failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_websocket_api.connect.assert_awaited_once_with(client_context())
    mock_websocket_api.stop_all_listeners.assert_not_awaited()
    mock_websocket_api.close.assert_not_awaited()
