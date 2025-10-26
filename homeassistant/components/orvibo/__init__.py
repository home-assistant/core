"""The orvibo component."""

from homeassistant import core

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .util import S20ConfigEntry

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: core.HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: S20ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
