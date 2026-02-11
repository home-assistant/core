"""Support for Amber Electric."""

import amberelectric

from homeassistant.components.sensor import ConfigType
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_SITE_ID, DOMAIN, PLATFORMS
from .coordinator import AmberConfigEntry, AmberUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Amber component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AmberConfigEntry) -> bool:
    """Set up Amber Electric from a config entry."""
    configuration = amberelectric.Configuration(access_token=entry.data[CONF_API_TOKEN])
    api_client = amberelectric.ApiClient(configuration)
    api_instance = amberelectric.AmberApi(api_client)
    site_id = entry.data[CONF_SITE_ID]

    coordinator = AmberUpdateCoordinator(hass, entry, api_instance, site_id)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmberConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
