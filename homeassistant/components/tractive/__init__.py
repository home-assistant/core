"""The tractive integration."""
from __future__ import annotations

import aiotractive

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["device_tracker"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tractive from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    client = aiotractive.Tractive(data[CONF_USERNAME], data[CONF_PASSWORD])

    tractive = TractiveClient(hass, client)
    tractive.subscribe()
    hass.data[DOMAIN][entry.entry_id] = tractive

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def cancel_listen_task(_):
        await tractive.unsubscribe()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        tractive = hass.data[DOMAIN].pop(entry.entry_id)
        await tractive.unsubscribe()
    return unload_ok


class TractiveClient:
    """A Tractive client."""

    def __init__(self, hass, client):
        """Initialize the client."""
        self._hass = hass
        self._client = client

    def subscribe(self):
        """Start event listener coroutine."""
        pass

    async def unsubscribe(self):
        """Stop event listener coroutine."""
        await self._client.close()
