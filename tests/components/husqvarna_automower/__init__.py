"""Tests for the Husqvarna Automower integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    # We lock the timezone, because the timezone is passed to the library to generate
    # some values like the next start sensor. This is needed, as the device is not aware
    # of its own timezone. So we assume the device is in the timezone selected in
    # the Home Assistant config.
    await hass.config.async_set_time_zone("Europe/Berlin")
    config_entry.add_to_hass(hass)
    ar.async_get(hass).async_get_or_create("Garden")
    await hass.config_entries.async_setup(config_entry.entry_id)
