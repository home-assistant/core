"""Tests for the Aladdin Connect Garage Door integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Aladdin Connect integration for testing."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
