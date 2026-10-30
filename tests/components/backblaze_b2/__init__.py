"""Tests for the Backblaze B2 integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the backblaze B2 integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
