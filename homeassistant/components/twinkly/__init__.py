"""The twinkly component."""

import asyncio

from aiohttp import ClientError
from ttls.client import Twinkly

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ENTRY_HOST, CONF_ENTRY_ID, DATA_CLIENT, DATA_DEVICE_INFO, DOMAIN

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entries from config flow."""
    hass.data.setdefault(DOMAIN, {})

    # We setup the client here so if at some point we add any other entity for this device,
    # we will be able to properly share the connection.
    uuid = entry.data[CONF_ENTRY_ID]
    host = entry.data[CONF_ENTRY_HOST]

    hass.data[DOMAIN].setdefault(uuid, {})

    client = Twinkly(host, async_get_clientsession(hass))

    try:
        device_info = await client.get_details()
    except (asyncio.TimeoutError, ClientError) as exception:
        raise ConfigEntryNotReady from exception

    hass.data[DOMAIN][uuid][DATA_CLIENT] = client
    hass.data[DOMAIN][uuid][DATA_DEVICE_INFO] = device_info

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove a twinkly entry."""

    # For now light entries don't have unload method, so we don't have to async_forward_entry_unload
    # However we still have to cleanup the shared client!
    uuid = entry.data[CONF_ENTRY_ID]
    hass.data[DOMAIN].pop(uuid)

    return True
