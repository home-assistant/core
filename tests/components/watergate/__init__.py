"""Tests for the Watergate integration."""

from homeassistant.core import HomeAssistant


async def init_integration(hass: HomeAssistant, mock_entry) -> None:
    """Set up the Watergate integration in Home Assistant."""
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
