"""The lastfm component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import LastFMConfigEntry, LastFMDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lastfm integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LastFMConfigEntry) -> None:
    """Set up lastfm from a config entry."""

    coordinator = LastFMDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LastFMConfigEntry) -> None:
    """Unload lastfm config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
