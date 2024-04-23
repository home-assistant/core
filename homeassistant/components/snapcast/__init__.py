"""Snapcast Integration."""

import logging

import snapcast.control

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .server import HomeAssistantSnapcast

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snapcast from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    try:
        server = await snapcast.control.create_server(
            hass.loop, host, port, reconnect=True
        )
    except OSError as ex:
        raise ConfigEntryNotReady(
            f"Could not connect to Snapcast server at {host}:{port}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantSnapcast(
        hass, server, f"{host}:{port}", entry.entry_id
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        snapcast_data = hass.data[DOMAIN].pop(entry.entry_id)
        # disconnect from server
        await snapcast_data.disconnect()
    return unload_ok
