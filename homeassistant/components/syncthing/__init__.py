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
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_USE_HTTPS,
    DOMAIN,
    EVENTS,
    RECONNECT_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
)

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

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    name = data[CONF_NAME]
    event_listener = EventListenerThread(hass, client, name)

    event_listener.start()

    @callback
    def stop_event_listener(_):
        event_listener.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_event_listener)

    hass.data[DOMAIN][name] = {
        "client": client,
        "event_listener": event_listener,
    }

    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=name)

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
        name = entry.data[CONF_NAME]
        hass.data[DOMAIN][name]["event_listener"].stop()
        hass.data[DOMAIN].pop(name)

    return unload_ok


class EventListenerThread(threading.Thread):
    """A threaded event listener class."""

    def __init__(self, hass, client, name):
        """Initialize the listener."""
        super().__init__()
        self._hass = hass
        self._client = client
        self._name = name
        self._events_stream = self._client.events()

    def run(self):
        """Listen to syncthing events."""
        server_was_unavailable = False

        # Python does not have the `retry` keyword, emulating it with a while loop
        while True:
            try:
                self._client.system.ping()
                if server_was_unavailable:
                    dispatcher_send(self._hass, f"{SERVER_AVAILABLE}-{self._name}")
                    server_was_unavailable = False

                for event in self._events_stream:
                    if self._events_stream.last_seen_id == 0:
                        continue  # skipping historical events from the first batch
                    if event["type"] not in EVENTS:
                        continue

                    signal_name = EVENTS[event["type"]]
                    folder = None
                    if "folder" in event["data"]:
                        folder = event["data"]["folder"]
                    else:  # A workaround, some events store folder id under `id` key
                        folder = event["data"]["id"]
                    dispatcher_send(
                        self._hass, f"{signal_name}-{self._name}-{folder}", event,
                    )
            except syncthing.SyncthingError:
                _LOGGER.info(
                    f"The syncthing event listener crashed. Probably, the server is not available. Sleeping {RECONNECT_INTERVAL.seconds} seconds and retrying..."
                )
                dispatcher_send(self._hass, f"{SERVER_UNAVAILABLE}-{self._name}")
                time.sleep(RECONNECT_INTERVAL.seconds)
                server_was_unavailable = True
                continue
            break

    def stop(self):
        """Stop listening to syncthing events."""
        self._events_stream.stop()
