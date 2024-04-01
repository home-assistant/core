"""Test the System Bridge integration."""

import asyncio
from unittest.mock import MagicMock

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)

from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.components.system_bridge.coordinator import (
    SystemBridgeDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_listener_authentication_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test listener authentication error."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    mock_websocket_client.listen.side_effect = AuthenticationException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_listener_connection_closed(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test listener connection closed."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    mock_websocket_client.listen.side_effect = ConnectionClosedException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_listener_connection_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test listener connection error."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    mock_websocket_client.listen.side_effect = ConnectionErrorException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_setup_authentication_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup authentication error."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    mock_websocket_client.connect.side_effect = AuthenticationException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup connection error."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    mock_websocket_client.connect.side_effect = ConnectionErrorException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_setup_timeout(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup timeout."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    mock_websocket_client.connect.side_effect = asyncio.TimeoutError

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_wait_timeout(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test wait timeout."""
    # Stop the listener from returning any data to trigger a timeout
    mock_websocket_client.listen.side_effect = None

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.SETUP_RETRY
