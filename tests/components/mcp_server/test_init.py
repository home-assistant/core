"""Test the Model Context Protocol Server init module."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the integration is initialized and can be unloaded cleanly."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
