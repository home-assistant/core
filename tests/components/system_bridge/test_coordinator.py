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

from . import mock_data_listener_bad, setup_integration

from tests.common import MockConfigEntry


async def test_listener_authentication_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test listener authentication error."""
    mock_websocket_client.listen.side_effect = AuthenticationException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        init_integration.entry_id
    ]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_listener_connection_closed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test listener connection closed."""
    mock_websocket_client.listen.side_effect = ConnectionClosedException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        init_integration.entry_id
    ]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_listener_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test listener connection error."""
    mock_websocket_client.listen.side_effect = ConnectionErrorException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        init_integration.entry_id
    ]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_setup_authentication_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setup authentication error."""
    mock_websocket_client.connect.side_effect = AuthenticationException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        init_integration.entry_id
    ]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_setup_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setup connection error."""
    mock_websocket_client.connect.side_effect = ConnectionErrorException

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        init_integration.entry_id
    ]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()


async def test_setup_timeout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test setup timeout."""
    mock_websocket_client.connect.side_effect = asyncio.TimeoutError

    # Ask the coordinator to update the data which will throw the exception
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        init_integration.entry_id
    ]
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

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_not_ready(
    hass: HomeAssistant,
    mock_version: MagicMock,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test not ready."""
    mock_websocket_client.listen.side_effect = mock_data_listener_bad

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
