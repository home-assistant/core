"""Implements the enasolar component."""
import logging

import pyenasolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the config entry."""
    host = config_entry.data[CONF_HOST]
    _LOGGER.debug("Instantiate an EnaSolar Inverter at '%s'", host)
    enasolar = pyenasolar.EnaSolar()

    try:
        await enasolar.interogate_inverter(host)
    except Exception as conerr:
        _LOGGER.error("Connection to EnaSolar Inverter '%s' failed (%s)", host, conerr)
        raise ConfigEntryNotReady from conerr

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)
