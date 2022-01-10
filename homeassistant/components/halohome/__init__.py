"""Integrate HALO Home into home assistant."""
import logging

import aiohttp
import halohome
from halohome import Connection, HaloHomeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_LOCATIONS, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HALO Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        locations = await halohome.list_devices(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except (HaloHomeError, OSError, aiohttp.ClientError) as exception:
        _LOGGER.error("Caught exception refreshing HALO devices: %s", exception)
        locations = entry.data[CONF_LOCATIONS]

    if locations != entry.data[CONF_LOCATIONS]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_LOCATIONS: locations}
        )

    hass.data[DOMAIN][entry.entry_id] = Connection(locations)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HALO Home config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
