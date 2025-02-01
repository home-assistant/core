"""Tests for the WLED integration."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wled import WLEDConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wled: AsyncMock
) -> None:
    """Test the WLED configuration entry unloading."""
    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable):
        connection_connected.set_result(None)
        await connection_finished

    # Mock out wled.listen with a Future
    mock_wled.listen.side_effect = connect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await connection_connected

    # Ensure config entry is loaded and are connected
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_wled.connect.call_count == 1
    assert mock_wled.disconnect.call_count == 0

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure everything is cleaned up nicely and are disconnected
    assert mock_wled.disconnect.call_count == 1


@patch(
    "homeassistant.components.wled.coordinator.WLED.request",
    side_effect=WLEDConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the WLED configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setting_unique_id(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test we set unique ID if not set yet."""
    assert init_integration.runtime_data
    assert init_integration.unique_id == "aabbccddeeff"
