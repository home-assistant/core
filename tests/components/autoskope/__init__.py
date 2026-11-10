"""Tests for Autoskope integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Autoskope integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
