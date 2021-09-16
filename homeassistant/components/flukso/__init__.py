"""The Flukso integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE_FIRMWARE, CONF_DEVICE_HASH, CONF_DEVICE_SERIAL, DOMAIN

PLATFORMS: list[str] = ["binary_sensor", "sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Create a Genius Hub system."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flukso from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = {
        "device": entry.data[CONF_DEVICE_HASH],
        "serial": entry.data[CONF_DEVICE_SERIAL],
        "firmware": entry.data[CONF_DEVICE_FIRMWARE],
        "sensor": {},
        "kube": {},
        "flx": {},
    }

    _LOGGER.debug(hass.data[DOMAIN])

    # await async_discover_sensors(hass, entry)

    # hass.data[DOMAIN][entry.entry_id] = "8cd3deb530d25404d77238bc24194cbc"

    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
