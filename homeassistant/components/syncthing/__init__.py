"""The syncthing integration."""
import asyncio
import logging

import aiosyncthing

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    EVENTS,
    RECONNECT_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up syncthing from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    name = data[CONF_NAME]

    client = aiosyncthing.Syncthing(
        data[CONF_TOKEN],
        url=data[CONF_URL],
        verify_ssl=data[CONF_VERIFY_SSL],
    )

    try:
        await client.system.ping()
    except aiosyncthing.exceptions.SyncthingError as exception:
        await client.close()
        raise ConfigEntryNotReady from exception

    syncthing = SyncthingClient(hass, client, name)

    syncthing.subscribe()

    hass.data[DOMAIN][name] = syncthing

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def cancel_listen_task(_):
        await syncthing.unsubscribe()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)

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
        await hass.data[DOMAIN][name].unsubscribe()
        hass.data[DOMAIN].pop(name)

    return unload_ok


class SyncthingClient:
    """A Syncthing client."""

    def __init__(self, hass, client, name):
        """Initialize the client."""
        self._hass = hass
        self._client = client
        self._name = name
        self._listen_task = None

    @property
    def database(self):
        """Get database namespace client."""
        return self._client.database

    @property
    def system(self):
        """Get system namespace client."""
        return self._client.system

    def subscribe(self):
        """Start event listener coroutine."""
        self._listen_task = self._hass.loop.create_task(self._listen())

    async def unsubscribe(self):
        """Stop event listener coroutine."""
        if self._listen_task:
            self._listen_task.cancel()
        await self._client.close()

    async def _listen(self):
        """Listen to Syncthing events."""
        events = self._client.events
        server_was_unavailable = False
        while True:
            try:
                await self._client.system.ping()
                if server_was_unavailable:
                    _LOGGER.info("The syncthing server '%s' is back online", self._name)
                    async_dispatcher_send(
                        self._hass, f"{SERVER_AVAILABLE}-{self._name}"
                    )
                    server_was_unavailable = False

                async for event in events.listen():
                    if events.last_seen_id == 0:
                        continue  # skipping historical events from the first batch
                    if event["type"] not in EVENTS:
                        continue

                    signal_name = EVENTS[event["type"]]
                    folder = None
                    if "folder" in event["data"]:
                        folder = event["data"]["folder"]
                    else:  # A workaround, some events store folder id under `id` key
                        folder = event["data"]["id"]
                    async_dispatcher_send(
                        self._hass,
                        f"{signal_name}-{self._name}-{folder}",
                        event,
                    )
                return
            except aiosyncthing.exceptions.SyncthingError:
                _LOGGER.info(
                    "The syncthing server '%s' is not available. Sleeping %i seconds and retrying",
                    self._name,
                    RECONNECT_INTERVAL.seconds,
                )
                async_dispatcher_send(self._hass, f"{SERVER_UNAVAILABLE}-{self._name}")
                await asyncio.sleep(RECONNECT_INTERVAL.seconds)
                server_was_unavailable = True
                continue
