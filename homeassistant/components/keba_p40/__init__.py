"""The KEBA P40 integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS

type KebaP40ConfigEntry = ConfigEntry[None]


async def async_setup_entry(hass: HomeAssistant, entry: KebaP40ConfigEntry) -> bool:
    """Set up KEBA P40 from a config entry."""
    entry.runtime_data = None
    raise ConfigEntryNotReady("Integration setup not yet implemented")


async def async_unload_entry(hass: HomeAssistant, entry: KebaP40ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
