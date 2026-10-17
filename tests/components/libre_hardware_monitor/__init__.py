"""Tests for the LibreHardwareMonitor integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Mock integration setup."""
    mock_config_entry.add_to_hass(hass)
    await setup_integration(hass, mock_config_entry)


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up a config entry that has already been added."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
