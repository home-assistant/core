"""The P1 Monitor integration."""
from __future__ import annotations

from p1monitor import P1Monitor, Phases, Settings, SmartMeter

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
)

PLATFORMS = (SENSOR_DOMAIN,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up P1 Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    client = P1Monitor(host=entry.data[CONF_HOST])

    async def update_smartmeter() -> SmartMeter:
        return await client.smartmeter()

    smartmeter: DataUpdateCoordinator[SmartMeter] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_SMARTMETER}",
        update_interval=SCAN_INTERVAL,
        update_method=update_smartmeter,
    )
    await smartmeter.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_SMARTMETER] = smartmeter

    async def update_phases() -> Phases:
        return await client.phases()

    phases: DataUpdateCoordinator[Phases] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_PHASES}",
        update_interval=SCAN_INTERVAL,
        update_method=update_phases,
    )
    await phases.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_PHASES] = phases

    async def update_settings() -> Settings:
        return await client.settings()

    settings: DataUpdateCoordinator[Settings] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_SETTINGS}",
        update_interval=SCAN_INTERVAL,
        update_method=update_settings,
    )
    await settings.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_SETTINGS] = settings

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload P1 Monitor config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
