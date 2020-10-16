"""The Aruba Instant integration."""
import asyncio
import logging

from requests.packages import urllib3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry, async_get_registry

from .virtual_controller import VirtualController
from .const import DOMAIN, AVAILABLE_CLIENTS, TRACKED_CLIENTS, SELECTED_CLIENTS

_LOGGER = logging.getLogger(__name__)
urllib3.disable_warnings()

PLATFORM = "device_tracker"
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = ["device_tracker"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Aruba Instant component."""
    _LOGGER.debug("Setting up the Aruba Instant component.")
    hass.data[DOMAIN] = config.get(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aruba Instant from a config entry."""
    _LOGGER.debug("Setting up the Aruba Instant config entry.")
    hass.data[DOMAIN].update({AVAILABLE_CLIENTS: {entry.entry_id: set()}})
    hass.data[DOMAIN].update(
        {TRACKED_CLIENTS: {entry.entry_id: entry.data.get(TRACKED_CLIENTS)}}
    )
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

    tracked_set = set(entry.data[TRACKED_CLIENTS])
    entity_registry = await async_get_registry(hass)
    if "track_none" not in entry.options.keys():
        # Start tracking new clients.
        for mac in entry.options.keys() - entry.data[TRACKED_CLIENTS]:
            _LOGGER.debug(  # pylint: disable=logging-format-interpolation
                f"Enabling entity: {mac}"
            )
            entry.data[TRACKED_CLIENTS].append(mac)

        # Stop tracking clients.
        for mac in entry.data[TRACKED_CLIENTS] - entry.options.keys():
            _LOGGER.debug(  # pylint: disable=logging-format-interpolation
                f"Disabling entity: {mac}"
            )
            client = hass.data[DOMAIN]["coordinator"][entry.entry_id].entities.get(mac)
            entity_registry.async_remove(
                entity_registry.async_get_entity_id(PLATFORM, DOMAIN, mac)
            )
            await client.async_remove()
            tracked_set.remove(mac)
            entry.data[TRACKED_CLIENTS].remove(mac)
    else:
        # Stop tracking all clients.
        _LOGGER.debug("Disabling all enabled entities.")
        entry.data[TRACKED_CLIENTS].clear()
        for mac in tracked_set:
            client = hass.data[DOMAIN]["coordinator"][entry.entry_id].entities.get(mac)
            await client.async_remove()
            entity_registry.async_remove(
                entity_registry.async_get_entity_id(PLATFORM, DOMAIN, mac)
            )
        tracked_set.clear()

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.debug("Removing Aruba Instant component.")
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
