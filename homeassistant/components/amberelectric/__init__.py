"""Support for Amber Electric."""

from amberelectric import ApiException, Configuration
from amberelectric.api import amber_api

from homeassistant.config_entries import ConfigEntry, ConfigError
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN, CONF_SITE_ID, DOMAIN, LOGGER, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Amber Electric from a config entry."""
    configuration = Configuration(access_token=entry.data[CONF_API_TOKEN])
    api_instance = amber_api.AmberApi.create(configuration)
    site_id = entry.data[CONF_SITE_ID]

    try:
        sites = await hass.async_add_executor_job(api_instance.get_sites)
        filtered = list(filter(lambda site: site.id == site_id, sites))
        if len(filtered) == 0:
            LOGGER.error("Site not found")
            return False

    except ApiException as api_exception:
        if api_exception.status == 403:
            LOGGER.error("API KEY Invalid")
            return False

        LOGGER.error("Unknown error: %s", api_exception.status)
        raise ConfigError from api_exception

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
