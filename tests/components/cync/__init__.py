"""Tests for the Cync integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Sets up the Cync integration to be used in testing."""
    config_entry.add_to_hass(hass)
    area_registry = ar.async_get(hass)
    for area in ("Bedroom", "Office"):
        area_registry.async_create(area)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
