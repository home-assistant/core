"""Tests for the IMGW-PIB integration."""

from tests.common import MockConfigEntry


async def init_integration(hass, config_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the IMGW-PIB integration in Home Assistant."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
