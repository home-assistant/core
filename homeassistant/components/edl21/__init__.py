"""The edl21 component."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    update_seconds = config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    _LOGGER.debug("Configured update interval: %s seconds", update_seconds)

    hass.data[DOMAIN][config_entry.entry_id] = {
        "update_interval_seconds": update_seconds,
        "config_entry": config_entry,
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(config_entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
