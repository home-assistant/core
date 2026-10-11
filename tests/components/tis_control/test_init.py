"""Test setting up and unloading TIS Control."""

from unittest.mock import MagicMock

from tis_smartbus import TISConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_gateway.close.assert_awaited_once()


async def test_setup_retries_when_port_unavailable(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried when the UDP port cannot be opened."""
    mock_gateway.connect.side_effect = TISConnectionError("port busy")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_first_read_fails(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A failure during the first read closes the connection and retries later."""
    mock_gateway.read_channels.side_effect = TISConnectionError("not connected")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_gateway.close.assert_awaited_once()
