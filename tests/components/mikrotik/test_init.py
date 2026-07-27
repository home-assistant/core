"""Test Mikrotik setup process."""

from unittest.mock import MagicMock

from librouteros.exceptions import ConnectionClosed, LibRouterosError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_successful_config_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test config entry successful setup."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED


async def test_hub_connection_error(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry
) -> None:
    """Test setup fails due to connection error."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_authentication_error(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry
) -> None:
    """Test setup fails due to authentication error."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = LibRouterosError("invalid user name or password")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading an entry."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
