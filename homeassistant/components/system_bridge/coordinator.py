"""DataUpdateCoordinator for System Bridge."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

from systembridgeconnector.const import TYPE_DATA_UPDATE
from systembridgeconnector.exceptions import (
    BadMessageException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

MODULES = [
    "battery",
    "cpu",
    "disk",
    "memory",
    # "network",
    "sensors",
    "system",
]


class SystemBridgeDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching System Bridge data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        LOGGER: logging.Logger,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global System Bridge data updater."""
        self.title = entry.title
        self.unsub: Callable | None = None
        self.websocket_client = WebSocketClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_API_KEY],
        )
        self.systembridge_data: dict = {}

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def async_handle_message(self, message: dict):
        """Handle messages from the WebSocket."""
        # No need to update anything, as everything is updated in the caller
        self.logger.debug("New message from %s: %s", self.title, message["type"])
        if message["type"] == TYPE_DATA_UPDATE:
            self.logger.debug("Set new data for: %s", message["module"])
            self.systembridge_data[message["module"]] = message["data"]
            self.async_set_updated_data(self.systembridge_data)

    async def _listen_for_events(self) -> None:
        """Listen for events from the WebSocket."""

        try:
            await self.websocket_client.register_data_listener(MODULES)
            await self.websocket_client.get_data(MODULES)
            await self.websocket_client.listen_for_messages(
                callback=self.async_handle_message
            )
        except ConnectionClosedException as exception:
            self.last_update_success = False
            self.logger.info(
                "Websocket Connection Closed for %s. Will retry: %s",
                self.title,
                exception,
            )
        except BadMessageException as exception:
            self.last_update_success = False
            self.update_listeners()
            self.logger.warning(
                "Exception occurred for %s. Will retry: %s",
                self.title,
                exception,
            )

    async def _setup_websocket(self) -> None:
        """Use WebSocket for updates."""

        try:
            await self.websocket_client.connect()
        except ConnectionErrorException as exception:
            if self.unsub:
                self.unsub()
                self.unsub = None
            raise ConfigEntryAuthFailed() from exception

        asyncio.create_task(self._listen_for_events())

        async def close_websocket(_) -> None:
            """Close WebSocket connection."""
            await self.websocket_client.close()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_websocket
        )

    async def _async_update_data(self) -> dict:
        """Update System Bridge data from WebSocket."""
        self.logger.debug(
            "_async_update_data - WebSocket Connected: %s",
            self.websocket_client.connected,
        )
        if not self.websocket_client.connected:
            await self._setup_websocket()

        return self.systembridge_data if self.systembridge_data is not None else {}
