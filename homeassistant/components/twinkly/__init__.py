"""The twinkly component."""

import twinkly_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ENTRY_HOST, CONF_ENTRY_ID, DOMAIN

PLATFORMS = ["light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entries from config flow."""

    # We setup the client here so if at some point we add any other entity for this device,
    # we will be able to properly share the connection.
    uuid = entry.data[CONF_ENTRY_ID]
    host = entry.data[CONF_ENTRY_HOST]

    hass.data.setdefault(DOMAIN, {})[uuid] = twinkly_client.TwinklyClient(
        host, async_get_clientsession(hass)
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove a twinkly entry."""

    # For now light entries don't have unload method, so we don't have to async_forward_entry_unload
    # However we still have to cleanup the shared client!
    uuid = entry.data[CONF_ENTRY_ID]
    hass.data[DOMAIN].pop(uuid)

    return True
