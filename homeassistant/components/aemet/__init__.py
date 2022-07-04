"""The AEMET OpenData component."""
from __future__ import annotations

import logging
from typing import Any

from aemet_opendata.interface import AEMET

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_STATION_UPDATES,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    FORECAST_MODES,
    PLATFORMS,
    RENAMED_FORECAST_SENSOR_KEYS,
)
from .weather_update_coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AEMET OpenData as config entry."""
    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)

    name = entry.data[CONF_NAME]
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    station_updates = entry.options.get(CONF_STATION_UPDATES, True)

    aemet = AEMET(api_key)
    weather_coordinator = WeatherUpdateCoordinator(
        hass, aemet, latitude, longitude, station_updates
    )

    await weather_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_NAME: name,
        ENTRY_WEATHER_COORDINATOR: weather_coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def async_migrate_entity_entry(entry: er.RegistryEntry) -> dict[str, Any] | None:
    """Migrate AEMET entity entries.

    - Migrates unique ID from old forecast sensors to the new unique ID
    """
    if entry.domain != Platform.SENSOR:
        return None
    for old_key, new_key in RENAMED_FORECAST_SENSOR_KEYS.items():
        for forecast_mode in FORECAST_MODES:
            old_suffix = f"-forecast-{forecast_mode}-{old_key}"
            if entry.unique_id.endswith(old_suffix):
                new_suffix = f"-forecast-{forecast_mode}-{new_key}"
                return {
                    "new_unique_id": entry.unique_id.replace(old_suffix, new_suffix)
                }

    # No migration needed
    return None
