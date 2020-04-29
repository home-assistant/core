"""The Met Office integration."""

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    METOFFICE_COORDINATOR,
    METOFFICE_DATA,
    METOFFICE_NAME,
)
from .data import MetOfficeData

_LOGGER = logging.getLogger(__name__)

_METOFFICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Required(CONF_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_METOFFICE_SCHEMA])}, extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["weather", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the National Weather Service (NWS) component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a Met Office entry."""

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    name = entry.data[CONF_NAME]

    metoffice_data = MetOfficeData(hass, api_key, latitude, longitude)
    await metoffice_data.async_update_site()

    metoffice_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"MetOffice Coordinator for {metoffice_data.site_name}",
        update_method=metoffice_data.async_update,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_DATA: metoffice_data,
        METOFFICE_COORDINATOR: metoffice_coordinator,
        METOFFICE_NAME: name,
    }

    # Fetch initial data so we have data when entities subscribe
    await metoffice_coordinator.async_refresh()

    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=f"{entry.data[CONF_LATITUDE]}_{entry.data[CONF_LONGITUDE]}"
        )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if len(hass.data[DOMAIN]) == 0:
            hass.data.pop(DOMAIN)
    return unload_ok
