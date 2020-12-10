"""The Niu integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)

from niu import NiuCloud
from niu import NiuAPIException, NiuNetException, NiuServerException

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# Want to support the sensor platform
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Niu component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Niu from a config entry."""

    # Get data from config
    config = entry.data
    username = entry.title
    password = config[CONF_PASSWORD]

    _LOGGER.error("Found Niu user: %s", username)
    _LOGGER.error("Found entry id: %s", entry.entry_id)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    # Store NiuCloud object in hass storage so it can be accessed by the platforms
    hass.data[DOMAIN][entry.entry_id] = NiuCloud(username=username, password=password)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
