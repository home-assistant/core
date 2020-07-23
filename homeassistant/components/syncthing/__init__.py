"""The syncthing integration."""
import asyncio
import logging
import threading
import time

import syncthing
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant

from .const import CONF_USE_HTTPS, DOMAIN, RECONNECT_INTERVAL

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the syncthing component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up syncthing from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    client = syncthing.Syncthing(
        data[CONF_TOKEN],
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        is_https=data[CONF_USE_HTTPS],
    )

    hass.data[DOMAIN][entry.entry_id] = client

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    event_thread = EventListenerThread(hass, client)

    def start_event_thread(_):
        event_thread.start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_event_thread)

    def stop_event_thread(_):
        event_thread.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_event_thread)

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


class EventListenerThread(threading.Thread):
    """A threaded event listener class."""

    def __init__(self, hass, client):
        """Initialize the listener."""
        super().__init__()
        self._hass = hass
        self._client = client
        self._events_stream = self._client.events()

    def run(self):
        """Listen to syncthing events."""
        _LOGGER.info("Starting the syncthing event listener...")

        # Python does not have the `retry` keyword, emulating it with a while loop
        while True:
            try:
                for event in self._events_stream:
                    _LOGGER.warn(event)
            except syncthing.SyncthingError:
                _LOGGER.info(
                    f"The syncthing event listener crashed. Probably, the server is not available. Sleeping {RECONNECT_INTERVAL.seconds} seconds and retrying..."
                )
                time.sleep(RECONNECT_INTERVAL.seconds)
                continue
            break

    def stop(self):
        """Stop listening to syncthing events."""
        _LOGGER.info("Stopping the syncthing event listener...")

        self._events_stream.stop()
        _LOGGER.info("The syncthing event listener stopped.")
