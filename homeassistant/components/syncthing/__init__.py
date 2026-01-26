"""The syncthing integration."""

import asyncio
import logging

import aiosyncthing

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DEVICE_EVENTS,
    DOMAIN,
    FOLDER_EVENTS,
    INITIAL_EVENTS_READY,
    RECONNECT_INTERVAL,
    SERVER_AVAILABLE,
    SERVER_UNAVAILABLE,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up syncthing from a config entry."""
    data = entry.data

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    client = aiosyncthing.Syncthing(
        data[CONF_TOKEN],
        url=data[CONF_URL],
        verify_ssl=data[CONF_VERIFY_SSL],
    )

    try:
        status = await client.system.status()
    except aiosyncthing.exceptions.SyncthingError as exception:
        await client.close()
        raise ConfigEntryNotReady from exception

    server_id = status["myID"]

    syncthing = SyncthingClient(hass, client, server_id)
    syncthing.subscribe()
    hass.data[DOMAIN][entry.entry_id] = syncthing

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def cancel_listen_task(_):
        await syncthing.unsubscribe()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_listen_task)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        syncthing = hass.data[DOMAIN].pop(entry.entry_id)
        await syncthing.unsubscribe()

    return unload_ok


class SyncthingClient:
    """A Syncthing client."""

    def __init__(self, hass, client, server_id):
        """Initialize the client."""
        self._hass = hass
        self._client = client
        self._server_id = server_id
        self._listen_task = None
        self._initial_events = []
        self._inital_events_processed = False

    @property
    def server_id(self) -> str:
        """Get server id."""
        return self._server_id

    @property
    def url(self) -> str:
        """Get server URL."""
        return self._client.url

    @property
    def database(self) -> aiosyncthing.Database:
        """Get database namespace client."""
        return self._client.database

    @property
    def system(self) -> aiosyncthing.System:
        """Get system namespace client."""
        return self._client.system

    @property
    def config(self) -> aiosyncthing.Config:
        """Get config namespace client."""
        return self._client.config

    def subscribe(self):
        """Start event listener coroutine."""
        self._listen_task = asyncio.create_task(self._listen())

    def get_initial_events(self) -> list:
        """Get initial events received upon subscription."""
        return self._initial_events

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
            if await self._server_available():
                if server_was_unavailable:
                    _LOGGER.warning(
                        "The syncthing server '%s' is back online", self._client.url
                    )
                    async_dispatcher_send(
                        self._hass, f"{SERVER_AVAILABLE}-{self._server_id}"
                    )
                    server_was_unavailable = False
            else:
                await asyncio.sleep(RECONNECT_INTERVAL.total_seconds())
                continue
            try:
                async for event in events.listen():
                    if events.last_seen_id == 0 and event["type"] in DEVICE_EVENTS:
                        # Storing initial events to find current device state
                        self._initial_events.append(event)
                        continue

                    # Triggering device status check once initial events are ready
                    if not self._inital_events_processed and events.last_seen_id != 0:
                        self._inital_events_processed = True
                        async_dispatcher_send(
                            self._hass,
                            f"{INITIAL_EVENTS_READY}-{self._server_id}",
                        )

                    if (
                        event["type"] not in FOLDER_EVENTS
                        and event["type"] not in DEVICE_EVENTS
                    ):
                        continue

                    if event["type"] in DEVICE_EVENTS:
                        signal_name = DEVICE_EVENTS[event["type"]]
                        device = event["data"].get("device") or event["data"]["id"]
                        async_dispatcher_send(
                            self._hass,
                            f"{signal_name}-{self._server_id}-{device}",
                            event,
                        )
                    elif event["type"] in FOLDER_EVENTS:
                        signal_name = FOLDER_EVENTS[event["type"]]
                        folder = event["data"].get("folder") or event["data"]["id"]
                        async_dispatcher_send(
                            self._hass,
                            f"{signal_name}-{self._server_id}-{folder}",
                            event,
                        )
            except aiosyncthing.exceptions.SyncthingError:
                _LOGGER.warning(
                    (
                        "The syncthing server '%s' is not available. Sleeping %i"
                        " seconds and retrying"
                    ),
                    self._client.url,
                    RECONNECT_INTERVAL.total_seconds(),
                )
                async_dispatcher_send(
                    self._hass, f"{SERVER_UNAVAILABLE}-{self._server_id}"
                )
                await asyncio.sleep(RECONNECT_INTERVAL.total_seconds())
                server_was_unavailable = True
                continue

    async def _server_available(self) -> bool:
        try:
            await self._client.system.ping()
        except aiosyncthing.exceptions.SyncthingError:
            return False

        return True
