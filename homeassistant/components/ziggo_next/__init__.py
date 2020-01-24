"""The Ziggo Next integration."""
import asyncio
import logging

import voluptuous as vol
from ziggonext import ZiggoNext

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_COUNTRY_CODE, DOMAIN, ZIGGO_API

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["media_player", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Ziggo Next component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Ziggo Next from a config entry."""
    api = ZiggoNext(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_COUNTRY_CODE],
    )
    api.initialize(_LOGGER, False)
    hass.data[ZIGGO_API] = api

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
    # if unload_ok:
    #     hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
