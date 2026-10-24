"""Tests for the SpaceXSI integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the SpaceXSI integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
