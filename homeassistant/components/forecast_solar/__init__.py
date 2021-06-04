"""The Forecast Solar integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
import forecast_solar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_AZIMUTH, CONF_DECLINATION, CONF_MODULES_POWER, DOMAIN

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Forecast Solar from a config entry."""
    await get_coordinator(hass, entry)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def get_coordinator(
    hass: HomeAssistant, entry: ConfigEntry
) -> DataUpdateCoordinator:
    """Get the data update coordinator."""
    if DOMAIN in hass.data:
        return hass.data[DOMAIN]

    async def async_get_forecast():
        with async_timeout.timeout(10):
            result = await forecast_solar.get_request(
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
                entry.data[CONF_AZIMUTH],
                entry.data[CONF_DECLINATION],
                entry.data[CONF_MODULES_POWER],
                aiohttp_client.async_get_clientsession(hass),
            )
            print(result)

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=async_get_forecast,
        update_interval=timedelta(minutes=20),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = coordinator
    return coordinator


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
