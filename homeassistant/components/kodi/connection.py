"""The connection of a Kodi config entry."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta
import logging
from typing import Any

from pykodi import CannotConnectError, Kodi, ProtocolError, TransportError
from pykodi.kodi import KodiHTTPConnection, KodiWSConnection

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started

_LOGGER = logging.getLogger(__name__)

WEBSOCKET_WATCHDOG_INTERVAL = timedelta(seconds=10)

SYSTEM_NOTIFICATIONS = ("System.OnQuit", "System.OnRestart", "System.OnSleep")

type KodiConfigEntry = ConfigEntry[KodiConnectionManager]


class KodiConnectionManager:
    """Keep the connection to Kodi open while the config entry is loaded.

    Over HTTP there is nothing to keep open. Over WebSocket a watchdog pings
    Kodi and connects again when the connection is lost.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KodiConfigEntry,
        connection: KodiHTTPConnection | KodiWSConnection,
        kodi: Kodi,
    ) -> None:
        """Initialize the connection manager."""
        self.hass = hass
        self.entry = entry
        self.connection = connection
        self.kodi = kodi
        # Read after each connect, None until then and after Kodi quits or a
        # connect, ping or version request fails
        self.version: str | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubscribe: list[Callable[[], None]] = []
        self._watchdog_task: asyncio.Task[None] | None = None
        self._connect_error = False

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Call the listener when the watchdog or Kodi quitting updates the version."""
        self._listeners.append(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(listener)

        return remove_listener

    async def async_setup(self) -> None:
        """Connect to Kodi, an unreachable Kodi is not an error."""
        if self.connection.can_subscribe:
            self._unsubscribe = [
                self.connection.subscribe(notification, self._async_on_quit)
                for notification in SYSTEM_NOTIFICATIONS
            ]
        # The watchdog retries over WebSocket and logs if that fails too
        with suppress(CannotConnectError, TransportError, ProtocolError):
            await self._async_connect()

    @callback
    def async_start(self) -> None:
        """Start the watchdog once Home Assistant has started."""
        if self.connection.can_subscribe:
            self.entry.async_on_unload(
                async_at_started(self.hass, self._async_start_watchdog)
            )

    async def async_stop(self, event: Event | None = None) -> None:
        """Stop the watchdog and close the connection."""
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        self._unsubscribe = []
        if self._watchdog_task is not None and not self._watchdog_task.done():
            # Otherwise a connect or ping cut short by the close is logged as a failure
            self._watchdog_task.cancel()
            await asyncio.wait([self._watchdog_task])
        await self.connection.close()

    @callback
    def _async_start_watchdog(self, hass: HomeAssistant) -> None:
        self._async_run_watchdog()
        self.entry.async_on_unload(
            async_track_time_interval(
                hass,
                self._async_run_watchdog,
                WEBSOCKET_WATCHDOG_INTERVAL,
                cancel_on_shutdown=True,
            )
        )

    @callback
    def _async_run_watchdog(self, now: datetime | None = None) -> None:
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = self.entry.async_create_background_task(
                self.hass, self._async_watchdog(), "kodi websocket watchdog"
            )

    async def _async_watchdog(self) -> None:
        """Ping Kodi, or connect again if the connection is lost."""
        if not self.connection.connected:
            try:
                await self._async_connect()
            except CannotConnectError, TransportError, ProtocolError:
                self._async_log_once("Unable to connect to Kodi via websocket")
                self._async_set_version(None)
                return
        else:
            message = "Unable to ping Kodi via websocket"
            try:
                await self.kodi.ping()
                if self.version is None:
                    message = "Unable to connect to Kodi via websocket"
                    await self._async_read_version()
            except CannotConnectError, TransportError, ProtocolError:
                self._async_log_once(message)
                self._async_set_version(None)
                await self.connection.close()
                return
        self._connect_error = False

    async def _async_connect(self) -> None:
        await self.connection.connect()
        if self.connection.can_subscribe:
            await self._async_read_version()

    async def _async_read_version(self) -> None:
        version = (await self.kodi.get_application_properties(["version"]))["version"]
        self._async_set_version(f"{version['major']}.{version['minor']}")

    async def _async_on_quit(self, sender: str, data: Any) -> None:
        """Close the connection when Kodi quits, restarts or sleeps."""
        self._async_set_version(None)
        await self.connection.close()

    @callback
    def _async_set_version(self, version: str | None) -> None:
        self.version = version
        for listener in list(self._listeners):
            listener()

    @callback
    def _async_log_once(self, message: str) -> None:
        if not self._connect_error:
            self._connect_error = True
            _LOGGER.warning(message)
