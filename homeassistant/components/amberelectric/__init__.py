"""Support for Amber Electric."""

from amberelectric import Configuration
from amberelectric.api import amber_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_SITE_ID, DOMAIN, PLATFORMS
from .coordinator import AmberUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Amber Electric from a config entry."""
    configuration = Configuration(access_token=entry.data[CONF_API_TOKEN])
    api_instance = amber_api.AmberApi.create(configuration)
    site_id = entry.data[CONF_SITE_ID]

    coordinator = AmberUpdateCoordinator(hass, api_instance, site_id)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
