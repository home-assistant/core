"""The P1 Monitor integration."""
from __future__ import annotations

from datetime import timedelta

from p1monitor import P1Monitor, Phases, Settings, SmartMeter

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_TIME_BETWEEN_UPDATE,
    DEFAULT_TIME_BETWEEN_UPDATE,
    DOMAIN,
    LOGGER,
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
)

PLATFORMS = (SENSOR_DOMAIN,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up P1 Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})

    client = P1Monitor(host=entry.data[CONF_HOST])

    min_time_between_updates = timedelta(
        seconds=entry.options.get(CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE)
    )

    """SmartMeter data."""

    async def update_smartmeter() -> SmartMeter:
        return await client.smartmeter()

    smartmeter: DataUpdateCoordinator[SmartMeter] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_SMARTMETER}",
        update_interval=min_time_between_updates,
        update_method=update_smartmeter,
    )
    await smartmeter.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_SMARTMETER] = smartmeter

    """Phases data."""

    async def update_phases() -> Phases:
        return await client.phases()

    phases: DataUpdateCoordinator[Phases] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_PHASES}",
        update_interval=min_time_between_updates,
        update_method=update_phases,
    )
    await phases.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_PHASES] = phases

    """Settings data."""

    async def update_settings() -> Settings:
        return await client.settings()

    settings: DataUpdateCoordinator[Settings] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{SERVICE_SETTINGS}",
        update_interval=min_time_between_updates,
        update_method=update_settings,
    )
    await settings.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id][SERVICE_SETTINGS] = settings

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload P1 Monitor config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
