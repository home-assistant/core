"""Tests for the SmartyPlants integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the SmartyPlants integration for testing."""
    config_entry.add_to_hass(hass)
    await setup_added_entry(hass, config_entry)


async def setup_added_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up an entry already added to Home Assistant.

    Adding it twice would exercise duplicate entry recovery instead of the
    setup the test is after.
    """
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
