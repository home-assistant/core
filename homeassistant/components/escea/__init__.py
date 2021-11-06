"""Platform for the Escea fireplace."""

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .discovery import async_start_discovery_service, async_stop_discovery_service

PLATFORMS = [CLIMATE_DOMAIN]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from YAML config - deprecated."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up from a config entry."""
    await async_start_discovery_service(hass)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Unload the config entry and stop discovery process."""
    await async_stop_discovery_service(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
