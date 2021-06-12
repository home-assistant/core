"""Support for Ambee."""
from __future__ import annotations

from ambee import Ambee

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL, SERVICE_AIR_QUALITY, SERVICE_POLLEN

PLATFORMS = (SENSOR_DOMAIN,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ambee from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    client = Ambee(
        api_key=entry.data[CONF_API_KEY],
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
    )

    for service in {SERVICE_AIR_QUALITY, SERVICE_POLLEN}:
        coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            update_method=getattr(client, service),
        )
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id][service] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ambee config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
