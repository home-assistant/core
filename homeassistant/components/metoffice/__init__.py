"""The Met Office integration."""

import logging

import datapoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_COORDINATOR,
    METOFFICE_NAME,
)
from .data import MetOfficeData
from .helpers import fetch_data, fetch_site

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Met Office entry."""

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    site_name = entry.data[CONF_NAME]

    connection = datapoint.connection(api_key=api_key)

    site = await hass.async_add_executor_job(
        fetch_site, connection, latitude, longitude
    )
    if site is None:
        raise ConfigEntryNotReady()

    async def async_update() -> MetOfficeData:
        return await hass.async_add_executor_job(fetch_data, connection, site)

    metoffice_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"MetOffice Coordinator for {site_name}",
        update_method=async_update,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_COORDINATOR: metoffice_coordinator,
        METOFFICE_NAME: site_name,
        METOFFICE_COORDINATES: f"{latitude}_{longitude}",
    }

    # Fetch initial data so we have data when entities subscribe
    await metoffice_coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
