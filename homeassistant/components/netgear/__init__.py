"""Support for Netgear routers."""
import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS
from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up Netgear integration."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Netgear component."""
    router = NetgearRouter(hass, entry)
    await router.async_setup()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = router

    entry.async_on_unload(entry.add_update_listener(update_listener))

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    router = hass.data[DOMAIN][entry.unique_id]

    if router._tracked_list:
        # Remove entities that are no longer tracked
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        for entity_entry in entries:
            if entity_entry.unique_id not in router._tracked_list:
                entity_registry.async_remove(entity_entry.entity_id)

        # Remove devices that are no longer tracked
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        for device_entry in devices:
            if dict(device_entry.connections)["mac"] not in router._tracked_list:
                device_registry.async_remove_device(device_entry.id)

    if unload_ok:
        await router.async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok

async def update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)