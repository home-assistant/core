"""The Met Office integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
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

PLATFORMS = ["sensor", "weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a Met Office entry."""

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    site_name = entry.data[CONF_NAME]

    metoffice_data = MetOfficeData(hass, api_key, latitude, longitude)
    await metoffice_data.async_update_site()
    if metoffice_data.site_name is None:
        raise ConfigEntryNotReady()

    metoffice_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"MetOffice Coordinator for {site_name}",
        update_method=metoffice_data.async_update,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    metoffice_hass_data = hass.data.setdefault(DOMAIN, {})
    metoffice_hass_data[entry.entry_id] = {
        METOFFICE_DATA: metoffice_data,
        METOFFICE_COORDINATOR: metoffice_coordinator,
        METOFFICE_NAME: site_name,
    }

    # Fetch initial data so we have data when entities subscribe
    await metoffice_coordinator.async_refresh()
    if metoffice_data.now is None:
        raise ConfigEntryNotReady()

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
