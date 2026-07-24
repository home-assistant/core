"""The Noonlight integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: NoonlightConfigEntry) -> bool:
    """Set up a Noonlight config entry."""
    coordinator = NoonlightCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NoonlightConfigEntry) -> bool:
    """Unload a Noonlight config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
