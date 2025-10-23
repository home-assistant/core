"""Tests for DayBetter Services integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(hass: HomeAssistant) -> ConfigEntry:
    """Set up the DayBetter Services integration in Home Assistant."""
    entry = MockConfigEntry(
        domain="daybetter_services",
        title="DayBetter Services",
        data={},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
