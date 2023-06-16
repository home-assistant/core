"""The openhome component."""

import asyncio
import logging

import aiohttp
from async_upnp_client.client import UpnpError
from openhomedevice.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .media_player import OpenhomeDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Forward to the same platform as async_setup_entry did
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up the configuration config entry."""
    _LOGGER.debug("Setting up config entry: %s", config_entry.unique_id)

    device = await hass.async_add_executor_job(Device, config_entry.data[CONF_HOST])

    try:
        await device.init()
    except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError) as exc:
        raise ConfigEntryNotReady from exc

    _LOGGER.debug("Initialised device: %s", device.uuid())

    entity = OpenhomeDevice(hass, device)

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = entity

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True
