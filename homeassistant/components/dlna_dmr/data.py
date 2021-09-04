"""Data used by this integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, NamedTuple, cast

from async_upnp_client import UpnpEventHandler, UpnpFactory, UpnpRequester
from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpSessionRequester

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, LOGGER


class EventListenAddr(NamedTuple):
    """Unique identifier for an event listener."""

    port: int  # Listening port, 0 means use an ephemeral port
    callback_url: str | None


class DlnaDmrData:
    """Storage class for domain global data."""

    lock: asyncio.Lock
    requester: UpnpRequester
    upnp_factory: UpnpFactory
    event_notifiers: dict[EventListenAddr, AiohttpNotifyServer]
    unmigrated_config: dict[str, Mapping[str, Any]]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global data."""
        self.lock = asyncio.Lock()
        session = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
        self.requester = AiohttpSessionRequester(session, with_sleep=False)
        self.upnp_factory = UpnpFactory(self.requester, non_strict=True)
        self.event_notifiers = {}
        self.unmigrated_config = {}

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)

    async def async_shutdown(self, event: Event) -> None:
        """Clean up resources when Home Assistant is stopped."""
        del event  # unused
        LOGGER.debug("Cleaning resources in DlnaDmrData")
        async with self.lock:
            tasks = (server.stop_server() for server in self.event_notifiers.values())
            asyncio.gather(*tasks)
            self.event_notifiers = {}

    async def async_get_event_notifier(
        self,
        listen_addr: EventListenAddr,
        loop: asyncio.AbstractEventLoop,
    ) -> UpnpEventHandler:
        """Return existing event notifier for the listen_addr, or create one.

        Only one event notify server is kept for each listen_addr.
        """
        LOGGER.debug("Getting event handler for %s", listen_addr)

        async with self.lock:
            # Return an existing event handler if we can
            if listen_addr in self.event_notifiers:
                return self.event_notifiers[listen_addr].event_handler

            # Start event handler
            server = AiohttpNotifyServer(
                requester=self.requester,
                listen_port=listen_addr.port,
                callback_url=listen_addr.callback_url,
                loop=loop,
            )
            await server.start_server()
            LOGGER.debug("Started event handler at %s", server.callback_url)

            self.event_notifiers[listen_addr] = server

        return server.event_handler


def get_domain_data(hass: HomeAssistant) -> DlnaDmrData:
    """Obtain this integration's domain data, creating it if needed."""
    if DOMAIN in hass.data:
        return cast(DlnaDmrData, hass.data[DOMAIN])

    data = DlnaDmrData(hass)
    hass.data[DOMAIN] = data
    return data
