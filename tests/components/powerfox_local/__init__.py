"""Tests for the Powerfox Local integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "1.1.1.1"
MOCK_API_KEY = "9x9x1f12xx3x"
MOCK_DEVICE_ID = MOCK_API_KEY


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
