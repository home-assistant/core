"""Support for Netgear routers."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

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

    if unload_ok:
        await hass.data[DOMAIN][entry.unique_id].async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok

async def update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
