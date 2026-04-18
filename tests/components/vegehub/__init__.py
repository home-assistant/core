"""Tests for the Vegetronix VegeHub integration."""

from homeassistant.components.vegehub.coordinator import VegeHubConfigEntry
from homeassistant.core import HomeAssistant


async def init_integration(
    hass: HomeAssistant,
    config_entry: VegeHubConfigEntry,
) -> None:
    """Load the VegeHub integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
