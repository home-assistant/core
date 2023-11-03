"""The ovos integration."""
from __future__ import annotations

import logging

from ovos_bus_client import MessageBusClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.NOTIFY]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ovos from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("entries", {})

    client = MessageBusClient(host=entry.data["host"], port=entry.data["port"])
    client.run_in_thread()

    hass.data[DOMAIN]["entries"][entry.entry_id] = {"client": client}

    discovery.load_platform(hass, Platform.NOTIFY, DOMAIN, {}, {})

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_id = entry.entry_id

        hass.data[DOMAIN]["entries"][entry_id]["client"].close()
        hass.data[DOMAIN]["entries"].pop(entry_id)

    return unload_ok
