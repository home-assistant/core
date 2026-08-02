"""Tests for Redfish config-entry lifecycle."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test all platforms set up and unload cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(init_integration.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.NOT_LOADED
