"""Tests for the Vegetronix VegeHub integration."""

from homeassistant.components.vegehub import VegeHubConfigEntry
from homeassistant.core import HomeAssistant


async def init_integration(
    hass: HomeAssistant,
    config_entry: VegeHubConfigEntry,
) -> None:
    """Load the VegeHub integration."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
