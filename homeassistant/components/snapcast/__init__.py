"""Snapcast Integration."""
import logging
import socket

import snapcast.control

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Snapcast from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data["host"]
    port = entry.data["port"]
    try:
        hass.data[DOMAIN][entry.entry_id] = await snapcast.control.create_server(
            hass.loop, host, port, reconnect=True
        )
    except socket.gaierror as ex:
        raise ConfigEntryNotReady(
            f"Could not connect to Snapcast server at {host}:{port}"
        ) from ex

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_forward_entry_unload(
        entry, "media_player"
    ):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
