"""Support for Enigma2 devices."""

import logging

from openwebif.api import OpenWebIfDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enigma2 from a config entry."""
    device: OpenWebIfDevice = OpenWebIfDevice(
        entry.options[CONF_HOST],
        port=entry.options[CONF_PORT],
        username=entry.options.get(CONF_USERNAME),
        password=entry.options.get(CONF_PASSWORD),
        is_https=entry.options.get(CONF_SSL),
    )
    entry.async_on_unload(device.close)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
