"""Websocket handler for UniFi Network integration."""

import asyncio

import aiohttp
import aiounifi

from homeassistant.core import callback

from ..const import LOGGER
from .connection import UnifiConnectionManager


class UnifiWebsocket:
    """Manages a single UniFi Network instance."""

    def __init__(self, connection: UnifiConnectionManager) -> None:
        """Initialize the system."""
        self.connection = connection
        self.hass = connection.hass
        self.api = connection.api

        self.ws_task: asyncio.Task[None] | None = None
        self.running = False

    @callback
    def start(self) -> None:
        """Start websocket handler."""
        self.running = True
        self.start_websocket()

    @callback
    def stop(self) -> None:
        """Stop websocket handler."""
        self.running = False
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
        if self.ws_task is not None and not self.ws_task.done():
            return

        async def _websocket_runner() -> None:
            """Start websocket."""
            try:
                await self.api.start_websocket()
            except (
                aiohttp.ClientConnectorError,
                aiohttp.WSServerHandshakeError,
            ) as err:
                LOGGER.debug("Websocket setup failed: %s", err)
            except aiounifi.WebsocketError as err:
                LOGGER.debug("Websocket disconnected: %s", err)

            self.connection.report_failure()

        self.ws_task = self.hass.loop.create_task(_websocket_runner())
