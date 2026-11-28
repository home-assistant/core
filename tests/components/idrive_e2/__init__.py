"""Tests for the IDrive e2 integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> bool:
    """Set up the IDrive e2 integration for testing."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return result
