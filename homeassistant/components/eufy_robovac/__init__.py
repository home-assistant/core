"""Support for Eufy RoboVac devices."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import EufyRoboVacConfigEntry, EufyRoboVacRuntimeData, PLATFORMS


async def async_setup_entry(
    hass: HomeAssistant, entry: EufyRoboVacConfigEntry
) -> bool:
    """Set up Eufy RoboVac from a config entry."""
    runtime_data: EufyRoboVacRuntimeData = {"dps": {}}
    entry.runtime_data = runtime_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EufyRoboVacConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data:
        entry.runtime_data["dps"] = {}
    return unload_ok
