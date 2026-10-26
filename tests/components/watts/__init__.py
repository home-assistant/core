"""Tests for the Watts Vision integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the Watts Vision integration for testing."""
    config_entry.add_to_hass(hass)
    area_registry = ar.async_get(hass)
    area_registry.async_create("Living Room")
    area_registry.async_create("Bedroom")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
