"""The P1 Monitor integration."""
from __future__ import annotations

from p1monitor import P1Monitor

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
    SERVICES,
)

PLATFORMS = (SENSOR_DOMAIN,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up P1 Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = P1Monitor(host=entry.data[CONF_HOST], session=session)

    async def _coordinator_update():
        data = {}
        data[SERVICE_SMARTMETER] = await client.smartmeter()
        data[SERVICE_PHASES] = await client.phases()
        data[SERVICE_SETTINGS] = await client.settings()
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}",
        update_interval=SCAN_INTERVAL,
        update_method=_coordinator_update,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload P1 Monitor config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client = hass.data[DOMAIN][entry.entry_id][SERVICES]
        client.close()
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
