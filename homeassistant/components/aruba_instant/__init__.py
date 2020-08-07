"""The Aruba Instant integration."""
import asyncio
import logging
from .VirtualController import VirtualController

from requests.packages import urllib3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
urllib3.disable_warnings()

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["device_tracker"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Aruba Instant component."""
    _LOGGER.debug(f"Setting up the Aruba Instant component.")
    hass.data[DOMAIN] = config.get(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aruba Instant from a config entry."""
    _LOGGER.debug(f"Setting up the Aruba Instant config entry.")
    hass.data[DOMAIN][entry.entry_id] = VirtualController(hass, entry)
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    # hass.data[DOMAIN].update({'unsub_device_tracker': {entry.entry_id: set()}})
    # hass.data[DOMAIN].update({'sub_device_tracker': {entry.entry_id: set()}})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.debug(f"Removing Aruba Instant component.")
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
