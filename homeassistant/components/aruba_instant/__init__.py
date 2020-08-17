"""The Aruba Instant integration."""
import asyncio
import logging
from .VirtualController import VirtualController

from requests.packages import urllib3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_registry import EntityRegistry
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
    entry.add_update_listener(async_update_options)
    hass.data[DOMAIN].update({"sub_device_tracker": {entry.entry_id: set()}})
    hass.data[DOMAIN].update({"discovered_devices": {entry.entry_id: set()}})
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle an options update."""
    tracked_set = set(hass.data[DOMAIN]['sub_device_tracker'][entry.entry_id])
    selected_set = set(entry.options.keys())
    if 'track_none' not in entry.options.keys():
        # Start tracking new clients.
        for client in selected_set:
            if client not in tracked_set:
                    _LOGGER.debug(f"Enabling entity: {client}")
                    EntityRegistry.async_update_entity(
                        hass.data["entity_registry"],
                        hass.data["entity_registry"].async_get_entity_id(
                            "device_tracker", DOMAIN, client
                        ),
                        disabled_by=None,
                    )
        # Stop tracking clients.
        for client in tracked_set.difference(selected_set):
            _LOGGER.debug(f"Disabling entity: {client}")
            EntityRegistry.async_update_entity(
                hass.data["entity_registry"],
                hass.data["entity_registry"].async_get_entity_id(
                    "device_tracker", DOMAIN, client
                ),
                disabled_by='user',
            )
            hass.data[DOMAIN]['sub_device_tracker'][entry.entry_id].remove(client)
    else:
        # Stop tracking all clients.
        _LOGGER.debug("Disabling all enabled entities.")
        for client in tracked_set:
            _LOGGER.debug(f"Disabling entity: {client}")
            EntityRegistry.async_update_entity(
                hass.data["entity_registry"],
                hass.data["entity_registry"].async_get_entity_id(
                    "device_tracker", DOMAIN, client
                ),
                disabled_by='user',
            )
            hass.data[DOMAIN]['sub_device_tracker'][entry.entry_id].remove(client)

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

