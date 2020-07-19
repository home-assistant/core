"""The syncthing integration."""
import asyncio

import syncthing
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_USE_HTTPS, DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the syncthing component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up syncthing from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = syncthing.Syncthing(
        data[CONF_TOKEN],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        is_https=data[CONF_USE_HTTPS],
    )

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
