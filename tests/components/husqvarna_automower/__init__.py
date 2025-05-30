"""Tests for the Husqvarna Automower integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    # We lock the timezone, because the timezone is passed to the library to generate
    # some values like the next start sensor. This is needed, as the device is not aware
    # of its own timezone. So we assume the device is in the timezone which is selected in
    # the Home Assistant config.
    await hass.config.async_set_time_zone("Europe/Berlin")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
