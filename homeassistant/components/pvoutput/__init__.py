"""The PVOutput integration."""
from __future__ import annotations

from pvo import PVOutput, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SYSTEM_ID, DOMAIN, LOGGER, PLATFORMS, SCAN_INTERVAL


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PVOutput from a config entry."""
    pvoutput = PVOutput(
        api_key=entry.data[CONF_API_KEY],
        system_id=entry.data[CONF_SYSTEM_ID],
        session=async_get_clientsession(hass),
    )

    coordinator: DataUpdateCoordinator[Status] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{entry.data[CONF_SYSTEM_ID]}",
        update_interval=SCAN_INTERVAL,
        update_method=pvoutput.status,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload PVOutput config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
