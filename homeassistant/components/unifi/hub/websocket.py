"""Websocket handler for UniFi Network integration."""

import asyncio
from datetime import datetime, timedelta

import aiohttp
import aiounifi

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from ..const import LOGGER
from .connection import UnifiConnectionManager

CHECK_WEBSOCKET_INTERVAL = timedelta(minutes=1)


class UnifiWebsocket:
    """Manages a single UniFi Network instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: aiounifi.Controller,
        connection: UnifiConnectionManager,
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.api = api
        self.connection = connection

        self.ws_task: asyncio.Task | None = None
        self._cancel_websocket_check: CALLBACK_TYPE | None = None

    @callback
    def start(self) -> None:
        """Start websocket handler."""
        self.connection.set_reconnect_callback(self.start_websocket)
        self._cancel_websocket_check = async_track_time_interval(
            self.hass, self._async_watch_websocket, CHECK_WEBSOCKET_INTERVAL
        )
        self.start_websocket()

    @callback
    def stop(self) -> None:
        """Stop websocket handler."""
        if self._cancel_websocket_check:
            self._cancel_websocket_check()
            self._cancel_websocket_check = None

        self.connection.set_reconnect_callback(None)

        if self.ws_task is not None:
            self.ws_task.cancel()

    async def stop_and_wait(self) -> None:
        """Stop websocket handler and await tasks."""
        self.stop()
        if self.ws_task is not None:
            _, pending = await asyncio.wait([self.ws_task], timeout=10)

            if pending:
                LOGGER.warning(
                    "Unloading UniFi Network (%s). Task %s did not complete in time",
                    self.api.connectivity.config.host,
                    self.ws_task,
                )

    @callback
    def start_websocket(self) -> None:
        """Start up connection to websocket."""

        async def _websocket_runner() -> None:
            """Start websocket."""
            try:
                await self.api.start_websocket()
            except aiohttp.ClientConnectorError, aiohttp.WSServerHandshakeError:
                LOGGER.error("Websocket setup failed")
            except aiounifi.WebsocketError:
                LOGGER.error("Websocket disconnected")

            self.connection.report_failure(log=True)

        self.ws_task = self.hass.loop.create_task(_websocket_runner())

    @callback
    def _async_watch_websocket(self, now: datetime) -> None:
        """Watch timestamp for last received websocket message."""
        LOGGER.debug(
            "Last received websocket timestamp: %s",
            self.api.connectivity.ws_message_received,
        )
