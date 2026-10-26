"""Tests for the Willow integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Willow integration for testing."""
    entry.add_to_hass(hass)
    ar.async_get(hass).async_create("Kitchen")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
