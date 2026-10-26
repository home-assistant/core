"""Tests for the Actron Air integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)
    ar.async_get(hass).async_create("Living Room")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
