"""Tests for Grandstream Home integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def init_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Grandstream Home integration in Home Assistant."""
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
