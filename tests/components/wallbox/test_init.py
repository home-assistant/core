"""Test Wallbox Init Component."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.components.wallbox import (
    entry,
    setup_integration,
    setup_integration_connection_error,
)


async def test_wallbox_setup_unload_entry(hass: HomeAssistant):
    """Test Wallbox Unload."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_unload_entry_connection_error(hass: HomeAssistant):
    """Test Wallbox Unload Connection Error."""

    await setup_integration_connection_error(hass)
    assert entry.state == ConfigEntryState.SETUP_RETRY

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED
