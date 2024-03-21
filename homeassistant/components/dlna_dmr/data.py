"""Data used by this integration."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import NamedTuple, cast

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester
from async_upnp_client.client import UpnpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.event_handler import UpnpEventHandler

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, LOGGER


class EventListenAddr(NamedTuple):
    """Unique identifier for an event listener."""

    host: str | None  # Specific local IP(v6) address for listening on
    port: int  # Listening port, 0 means use an ephemeral port
    callback_url: str | None


class DlnaDmrData:
    """Storage class for domain global data."""

    lock: asyncio.Lock
    requester: UpnpRequester
    upnp_factory: UpnpFactory
    event_notifiers: dict[EventListenAddr, AiohttpNotifyServer]
    event_notifier_refs: defaultdict[EventListenAddr, int]
    stop_listener_remove: CALLBACK_TYPE | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global data."""
        self.lock = asyncio.Lock()
        session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
        self.requester = AiohttpSessionRequester(session, with_sleep=True)
        self.upnp_factory = UpnpFactory(self.requester, non_strict=True)
        self.event_notifiers = {}
        self.event_notifier_refs = defaultdict(int)

    async def async_cleanup_event_notifiers(self, event: Event) -> None:
        """Clean up resources when Home Assistant is stopped."""
        LOGGER.debug("Cleaning resources in DlnaDmrData")
        async with self.lock:
            tasks = (
                server.async_stop_server() for server in self.event_notifiers.values()
            )
            asyncio.gather(*tasks)
            self.event_notifiers = {}
            self.event_notifier_refs = defaultdict(int)

    async def async_get_event_notifier(
        self, listen_addr: EventListenAddr, hass: HomeAssistant
    ) -> UpnpEventHandler:
        """Return existing event notifier for the listen_addr, or create one.

        Only one event notify server is kept for each listen_addr. Must call
        async_release_event_notifier when done to cleanup resources.
        """
        LOGGER.debug("Getting event handler for %s", listen_addr)

        async with self.lock:
            # Stop all servers when HA shuts down, to release resources on devices
            if not self.stop_listener_remove:
                self.stop_listener_remove = hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, self.async_cleanup_event_notifiers
                )

            # Always increment the reference counter, for existing or new event handlers
            self.event_notifier_refs[listen_addr] += 1

            # Return an existing event handler if we can
            if listen_addr in self.event_notifiers:
                return self.event_notifiers[listen_addr].event_handler

            # Start event handler
            source = (listen_addr.host or "0.0.0.0", listen_addr.port)
            server = AiohttpNotifyServer(
                requester=self.requester,
                source=source,
                callback_url=listen_addr.callback_url,
                loop=hass.loop,
            )
            await server.async_start_server()
            LOGGER.debug("Started event handler at %s", server.callback_url)

            self.event_notifiers[listen_addr] = server

        return server.event_handler

    async def async_release_event_notifier(self, listen_addr: EventListenAddr) -> None:
        """Indicate that the event notifier for listen_addr is not used anymore.

        This is called once by each caller of async_get_event_notifier, and will
        stop the listening server when all users are done.
        """
        async with self.lock:
            assert self.event_notifier_refs[listen_addr] > 0
            self.event_notifier_refs[listen_addr] -= 1

            # Shutdown the server when it has no more users
            if self.event_notifier_refs[listen_addr] == 0:
                server = self.event_notifiers.pop(listen_addr)
                await server.async_stop_server()

            # Remove the cleanup listener when there's nothing left to cleanup
            if not self.event_notifiers:
                assert self.stop_listener_remove is not None
                self.stop_listener_remove()
                self.stop_listener_remove = None


def get_domain_data(hass: HomeAssistant) -> DlnaDmrData:
    """Obtain this integration's domain data, creating it if needed."""
    if DOMAIN in hass.data:
        return cast(DlnaDmrData, hass.data[DOMAIN])

    data = DlnaDmrData(hass)
    hass.data[DOMAIN] = data
    return data
