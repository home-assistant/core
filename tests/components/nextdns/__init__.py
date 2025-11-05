"""Tests for the NextDNS integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the NextDNS integration in Home Assistant."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
