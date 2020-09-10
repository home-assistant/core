"""The Aruba Instant integration."""
import asyncio
import logging

from requests.packages import urllib3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry, async_get_registry

from .VirtualController import VirtualController
from .const import DOMAIN, DISCOVERED_DEVICES, TRACKED_DEVICES

_LOGGER = logging.getLogger(__name__)
urllib3.disable_warnings()

PLATFORM = "device_tracker"
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = ["device_tracker"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Aruba Instant component."""
    _LOGGER.debug(f"Setting up the Aruba Instant component.")
    hass.data[DOMAIN] = config.get(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aruba Instant from a config entry."""
    _LOGGER.debug(f"Setting up the Aruba Instant config entry.")
    hass.data[DOMAIN].update({DISCOVERED_DEVICES: {entry.entry_id: set()}})
    hass.data[DOMAIN].update({TRACKED_DEVICES: {entry.entry_id: set()}})
    hass.data[DOMAIN][entry.entry_id] = VirtualController(hass, entry)
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    if not entry.update_listeners:
        entry.add_update_listener(async_update_options)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle an options update."""

    tracked_set = set(entry.data["clients"])
    selected_set = set(entry.options.keys())
    entity_registry = await async_get_registry(hass)
    if "track_none" not in entry.options.keys():
        # Start tracking new clients.
        for mac in selected_set:
            if mac not in tracked_set:
                _LOGGER.debug(f"Enabling entity: {mac}")
                entry.data["clients"].append(mac)

        # Stop tracking clients.
        for mac in tracked_set.difference(selected_set):
            _LOGGER.debug(f"Disabling entity: {mac}")
            entry.data["clients"].remove(mac)
            tracked_set = set(entry.data["clients"])
            client = hass.data[DOMAIN]['coordinator'][entry.entry_id].entities.get(mac)
            await client.async_remove()
            entity_registry.async_remove(entity_registry.async_get_entity_id(PLATFORM, DOMAIN, mac))
    else:
        # Stop tracking all clients.
        _LOGGER.debug("Disabling all enabled entities.")
        entry.data["clients"].clear()
        for mac in tracked_set:
            client = hass.data[DOMAIN]['coordinator'][entry.entry_id].entities.get(mac)
            await client.async_remove()
            entity_registry.async_remove(entity_registry.async_get_entity_id(PLATFORM, DOMAIN, mac))
    await hass.config_entries.async_reload(entry.entry_id)


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
