"""The Niu integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from niu import NiuCloud

from .const import DOMAIN

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

    # First have to define the domain
    hass.data[DOMAIN] = {}

    # Store NiuCloud object in hass storage so it can be accessed by the platforms
    hass.data[DOMAIN][entry.entry_id] = NiuCloud(username=username, password=password)

    # Setup the platforms
    for component in PLATFORMS:
        hass.async_create_task(
            # Create task to add the entities from a platform
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
