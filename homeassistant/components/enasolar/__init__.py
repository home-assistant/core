"""Implements the enasolar component."""
import logging

import pyenasolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the config entry."""
    host = config_entry.data[CONF_HOST]
    enasolar = pyenasolar.EnaSolar()

    try:
        await enasolar.interogate_inverter(host)
    except Exception as conerr:
        raise ConfigEntryNotReady(
            f"Connection to EnaSolar Inverter '{host}' failed ({conerr})"
        ) from conerr

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = enasolar
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        del hass.data[DOMAIN][config_entry.entry_id]
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)
