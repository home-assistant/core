"""Support for Twente Milieu."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TwenteMilieuConfigEntry, TwenteMilieuDataUpdateCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> bool:
    """Set up Twente Milieu from a config entry."""
    coordinator = TwenteMilieuDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> bool:
    """Unload Twente Milieu config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
