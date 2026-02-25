"""Support for Eufy RoboVac devices."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, EufyRoboVacRuntimeData, PLATFORMS

type EufyRoboVacConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant, entry: EufyRoboVacConfigEntry
) -> bool:
    """Set up Eufy RoboVac from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    runtime_data: EufyRoboVacRuntimeData = hass.data[DOMAIN]
    runtime_data[entry.entry_id] = {"dps": {}}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EufyRoboVacConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
