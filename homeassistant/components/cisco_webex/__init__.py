"""The cisco_webex integration."""
import asyncio

import voluptuous as vol
from webexteamssdk import WebexTeamsAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import API, DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the cisco_webex component."""

    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up cisco_webex from a config entry."""
    hass.data[DOMAIN][entry.unique_id] = {
        CONF_TOKEN: entry.data[CONF_TOKEN],
        API: WebexTeamsAPI(access_token=entry.data[CONF_TOKEN]),
    }

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
        hass.data[DOMAIN].pop(entry.unique_id)

    return unload_ok
