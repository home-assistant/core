"""Support for Amber Electric."""

import logging

from amberelectric import ApiException, Configuration
from amberelectric.api import amber_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_API_TOKEN, CONF_SITE_ID, DOMAIN

PLATFORMS = ["sensor"]
LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Amber Electric from a config entry."""
    configuration = Configuration(access_token=entry.data.get(CONF_API_TOKEN))
    api_instance = amber_api.AmberApi.create(configuration)

    try:
        site_id = entry.data.get(CONF_SITE_ID)
        sites = await hass.async_add_executor_job(api_instance.get_sites)
        filtered = list(filter(lambda site: site.id == site_id, sites))
        if len(filtered) == 0:
            LOGGER.error("Site not found")
            raise ConfigEntryNotReady

    except ApiException as e:
        if e.status == 403:
            LOGGER.error("API KEY Invalid")
            raise ConfigEntryNotReady
        else:
            LOGGER.error("Unknown error")
            raise ConfigEntryNotReady

    hass.data[DOMAIN] = {"entry": entry}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
