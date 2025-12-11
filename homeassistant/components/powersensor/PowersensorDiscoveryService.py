"""Utilities to support zeroconf discovery of new plugs on the network."""

import asyncio
from contextlib import suppress
import logging

from zeroconf import BadTypeInNameException, ServiceBrowser, ServiceListener, Zeroconf
from zeroconf.asyncio import AsyncServiceInfo

import homeassistant.components.zeroconf
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.loader import bind_hass

from .const import (
    ZEROCONF_ADD_PLUG_SIGNAL,
    ZEROCONF_REMOVE_PLUG_SIGNAL,
    ZEROCONF_UPDATE_PLUG_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)


class PowersensorServiceListener(ServiceListener):
    """A zeroconf service listener that handles the discovery of plugs and signals the dispatcher."""

    def __init__(self, hass: HomeAssistant, debounce_timeout: float = 60) -> None:
        """Initialize the listener, set up various buffers to hold info."""
        self._hass = hass
        self._plugs: dict[str, dict] = {}
        self._discoveries: dict[str, AsyncServiceInfo] = {}
        self._pending_removals: dict[str, asyncio.Task] = {}
        self._debounce_seconds = debounce_timeout

    def add_service(self, zc, type_, name):
        """Handle zeroconf messages for adding new devices."""
        self.cancel_any_pending_removal(name, "request to add")
        info = self.__add_plug(zc, type_, name)
        if info:
            asyncio.run_coroutine_threadsafe(
                self._async_service_add(self._plugs[name]), self._hass.loop
            )

    async def _async_service_add(self, *args):
        """Send add signal to dispatcher."""
        self.dispatch(ZEROCONF_ADD_PLUG_SIGNAL, *args)

    async def _async_delayed_remove(self, name):
        """Actually process the removal after delay."""
        try:
            await asyncio.sleep(self._debounce_seconds)
            _LOGGER.info(
                "Request to remove service %s still pending after timeout. Processing remove request... ",
                name,
            )
            if name in self._plugs:
                data = self._plugs[name].copy()
                del self._plugs[name]
            else:
                data = None
            asyncio.run_coroutine_threadsafe(
                self._async_service_remove(name, data), self._hass.loop
            )
        except asyncio.CancelledError:
            # Task was cancelled because service came back
            _LOGGER.info(
                "Request to remove service %s was canceled by request to update or add plug. ",
                name,
            )
            raise
        finally:
            # Either way were done with this task
            self._pending_removals.pop(name, None)

    def remove_service(self, zc, type_, name):
        """Handle zeroconf messages for removal of devices."""
        if name in self._pending_removals:
            # removal for this service is already pending
            return

        _LOGGER.info("Scheduling removal for %s", name)
        self._pending_removals[name] = asyncio.run_coroutine_threadsafe(
            self._async_delayed_remove(name), self._hass.loop
        )

    async def _async_service_remove(self, *args):
        """Send remove signal to dispatcher."""
        self.dispatch(ZEROCONF_REMOVE_PLUG_SIGNAL, *args)

    def update_service(self, zc, type_, name):
        """Handle zeroconf messages for updating device info."""
        self.cancel_any_pending_removal(name, "request to update")
        info = self.__add_plug(zc, type_, name)
        if info:
            asyncio.run_coroutine_threadsafe(
                self._async_service_update(self._plugs[name]), self._hass.loop
            )

    async def _async_service_update(self, *args):
        """Send update signal to dispatcher."""
        # remove from pending tasks if update received
        self.dispatch(ZEROCONF_UPDATE_PLUG_SIGNAL, *args)

    async def _async_get_service_info(self, zc, type_, name):
        try:
            info = await zc.async_get_service_info(type_, name, timeout=3000)
            self._discoveries[name] = info
        except (
            TimeoutError,
            OSError,
            BadTypeInNameException,
            NotImplementedError,
        ) as err:  # expected possible exceptions
            _LOGGER.error("Error retrieving info for %s: %s", name, err)

    def __add_plug(self, zc, type_, name):
        info = zc.get_service_info(type_, name)

        if info:
            self._plugs[name] = {
                "type": type_,
                "name": name,
                "addresses": [
                    ".".join(str(b) for b in addr) for addr in info.addresses
                ],
                "port": info.port,
                "server": info.server,
                "properties": info.properties,
            }
        return info

    def cancel_any_pending_removal(self, name, source):
        """Cancel pending removal and don't send to dispatcher."""
        task = self._pending_removals.pop(name, None)
        if task:
            task.cancel()
            _LOGGER.info("Cancelled pending removal for %s by %s. ", name, source)

    @callback
    @bind_hass
    def dispatch(self, signal_name, *args):
        """Send signal to dispatcher."""
        async_dispatcher_send(self._hass, signal_name, *args)


class PowersensorDiscoveryService:
    """A zeroconf service that handles the discovery of plugs."""

    def __init__(
        self, hass: HomeAssistant, service_type: str = "_powersensor._tcp.local."
    ) -> None:
        """Constructor for zeroconf service that handles the discovery of plugs."""
        self._hass = hass
        self.service_type = service_type

        self.zc: Zeroconf | None = None
        self.listener: PowersensorServiceListener | None = None
        self.browser: ServiceBrowser | None = None
        self.running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the mDNS discovery service."""
        if self.running:
            return

        self.running = True
        self.zc = await homeassistant.components.zeroconf.async_get_instance(self._hass)
        self.listener = PowersensorServiceListener(self._hass)

        # Create browser
        self.browser = ServiceBrowser(self.zc, self.service_type, self.listener)

        # Start the background task
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        """Background task that keeps the service alive."""
        with suppress(asyncio.CancelledError):
            while self.running:
                await asyncio.sleep(1)

    async def stop(self):
        """Stop the mDNS discovery service."""
        self.running = False

        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

        if self.zc:
            # self.zc.close()
            self.zc = None

        self.browser = None
        self.listener = None
