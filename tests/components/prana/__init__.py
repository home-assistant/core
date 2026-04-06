"""Mock inputs for Prana tests."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def async_init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the Prana integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
