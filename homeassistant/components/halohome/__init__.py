"""Integrate HALO Home into home assistant."""
from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

LOGGER = logging.getLogger(__name__)


@dataclass
class HaloHomeData:
    """HALO Home Config Entry."""

    host: str
    username: str
    password: str


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HALO Home from a config entry."""
    data = hass.data.setdefault(DOMAIN, {})
    data[entry.entry_id] = HaloHomeData(**entry.data)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HALO Home config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
