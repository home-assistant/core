"""Platform for the Escea fireplace."""

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .discovery import async_start_discovery_service, async_stop_discovery_service

PLATFORMS = [CLIMATE_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up from a config entry."""
    await async_start_discovery_service(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload the config entry and stop discovery process."""
    await async_stop_discovery_service(hass)
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
