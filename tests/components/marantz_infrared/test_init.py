"""Tests for the Marantz Infrared integration setup."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
