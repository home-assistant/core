"""Websocket handler for UniFi Network integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import aiohttp
import aiounifi

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from ..const import LOGGER

RETRY_TIMER = 15
CHECK_WEBSOCKET_INTERVAL = timedelta(minutes=1)


class UnifiWebsocket:
    """Manages a single UniFi Network instance."""

    def __init__(
        self, hass: HomeAssistant, api: aiounifi.Controller, signal: str
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.api = api
        self.signal = signal

        self.ws_task: asyncio.Task | None = None
        self._cancel_websocket_check: CALLBACK_TYPE | None = None

        self.available = True

    @callback
    def start(self) -> None:
        """Start websocket handler."""
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

        if self.ws_task is not None:
            self.ws_task.cancel()

    async def stop_and_wait(self) -> None:
        """Stop websocket handler and await tasks."""
        if self._cancel_websocket_check:
            self._cancel_websocket_check()
            self._cancel_websocket_check = None

        if self.ws_task is not None:
            self.stop()

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
            except (aiohttp.ClientConnectorError, aiohttp.WSServerHandshakeError):
                LOGGER.error("Websocket setup failed")
            except aiounifi.WebsocketError:
                LOGGER.error("Websocket disconnected")

            self.available = False
            async_dispatcher_send(self.hass, self.signal)
            self.hass.loop.call_later(RETRY_TIMER, self.reconnect, True)

        if not self.available:
            self.available = True
            async_dispatcher_send(self.hass, self.signal)

        self.ws_task = self.hass.loop.create_task(_websocket_runner())

    @callback
    def reconnect(self, log: bool = False) -> None:
        """Prepare to reconnect UniFi session."""

        async def _reconnect() -> None:
            """Try to reconnect UniFi Network session."""
            try:
                async with asyncio.timeout(5):
                    await self.api.login()

            except (
                TimeoutError,
                aiounifi.BadGateway,
                aiounifi.ServiceUnavailable,
                aiounifi.AiounifiException,
            ) as exc:
                LOGGER.debug("Schedule reconnect to UniFi Network '%s'", exc)
                self.hass.loop.call_later(RETRY_TIMER, self.reconnect)

            else:
                self.start_websocket()

        if log:
            LOGGER.info("Will try to reconnect to UniFi Network")

        self.hass.loop.create_task(_reconnect())

    @callback
    def _async_watch_websocket(self, now: datetime) -> None:
        """Watch timestamp for last received websocket message."""
        LOGGER.debug(
            "Last received websocket timestamp: %s",
            self.api.connectivity.ws_message_received,
        )
