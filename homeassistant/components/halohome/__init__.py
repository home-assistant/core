"""Integrate HALO Home into home assistant."""
import logging

from halohome import Connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LOCATIONS, DOMAIN, PLATFORMS

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HALO Home from a config entry."""
    config = entry.data
    location_devices = config[CONF_LOCATIONS]

    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = Connection(location_devices)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HALO Home config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
