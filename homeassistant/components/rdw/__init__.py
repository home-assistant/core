"""Support for RDW."""

from __future__ import annotations

from vehicle import RDW, Vehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LICENSE_PLATE, DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RDW from a config entry."""
    session = async_get_clientsession(hass)
    rdw = RDW(session=session, license_plate=entry.data[CONF_LICENSE_PLATE])

    coordinator: DataUpdateCoordinator[Vehicle] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_APK",
        update_interval=SCAN_INTERVAL,
        update_method=rdw.vehicle,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload RDW config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
