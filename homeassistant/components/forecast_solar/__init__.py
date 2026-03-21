"""The Forecast.Solar integration."""

from __future__ import annotations

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DAMPING,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_MODULES_POWER,
)
from .coordinator import ForecastSolarConfigEntry, ForecastSolarDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_migrate_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Migrate old config entry."""

    if entry.version == 1:
        # v1 -> v2: rename "modules power" key and split single damping value
        # into separate morning/evening values.
        damping = entry.options.get(CONF_DAMPING, 0.0)
        new_options = entry.options.copy()
        new_options.pop(CONF_DAMPING)
        new_options |= {
            CONF_MODULES_POWER: new_options.pop("modules power"),
            CONF_DAMPING_MORNING: damping,
            CONF_DAMPING_EVENING: damping,
        }
        hass.config_entries.async_update_entry(entry, options=new_options, version=2)

    if entry.version == 2:
        # v2 -> v3: location is now always stored in options.
        # Previously, entries using the home location stored a flag in entry.data
        # and omitted lat/lon from options entirely. Backfill from hass.config.
        new_options = entry.options.copy()
        if CONF_LATITUDE not in new_options:
            new_options[CONF_LATITUDE] = hass.config.latitude
        if CONF_LONGITUDE not in new_options:
            new_options[CONF_LONGITUDE] = hass.config.longitude
        hass.config_entries.async_update_entry(
            entry, options=new_options, data={}, version=3
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Set up Forecast.Solar from a config entry."""
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ForecastSolarConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
