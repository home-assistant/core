"""Tests for the wmspro integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> bool:
    """Set up a config entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return result
