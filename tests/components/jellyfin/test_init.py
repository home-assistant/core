"""Test the initialization of the Jellyfin component."""

from homeassistant.components.jellyfin.client_wrapper import CannotConnect, InvalidAuth
from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from . import setup_mock_jellyfin_config_entry


async def test_setup_entry(hass):
    """Test successful load of a ConfigEntry."""
    await setup_mock_jellyfin_config_entry(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_no_connection(hass):
    """Test unsuccessful load of a ConfigEntry due to connection issue."""
    await setup_mock_jellyfin_config_entry(hass, CannotConnect)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_authentication_failure(hass):
    """Test unsuccessful load of a ConfigEntry due to authentication issue."""
    await setup_mock_jellyfin_config_entry(hass, None, InvalidAuth)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass):
    """Test successful unload of a ConfigEntry."""
    await setup_mock_jellyfin_config_entry(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED
