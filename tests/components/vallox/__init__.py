"""Tests for the Vallox integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

TEST_HOST = "192.168.100.50"
TEST_NAME = "Vallox"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Vallox integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
