"""Tests for JVC Projector integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 20554
MOCK_PASSWORD = "jvcpasswd"
MOCK_MAC = "jvcmac"
MOCK_MODEL = "jvcmodelNZ"


# used to load a single platform in a test
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
