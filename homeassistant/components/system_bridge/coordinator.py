"""DataUpdateCoordinator for System Bridge."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

from systembridgeconnector.const import (
    EVENT_DATA,
    EVENT_MESSAGE,
    EVENT_MODULE,
    EVENT_SUBTYPE,
    EVENT_TYPE,
    SUBTYPE_BAD_API_KEY,
    TYPE_DATA_UPDATE,
    TYPE_ERROR,
)
from systembridgeconnector.exceptions import (
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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

MODULES = [
    "battery",
    "cpu",
    "disk",
    "display",
    "gpu",
    "memory",
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
        self.logger.debug("New message from %s: %s", self.title, message[EVENT_TYPE])
        if message[EVENT_TYPE] == TYPE_DATA_UPDATE:
            self.logger.debug("Set new data for: %s", message[EVENT_MODULE])
            self.systembridge_data[message[EVENT_MODULE]] = message[EVENT_DATA]
            self.async_set_updated_data(self.systembridge_data)
        elif message[EVENT_TYPE] == TYPE_ERROR:
            if message[EVENT_SUBTYPE] == SUBTYPE_BAD_API_KEY:
                self.logger.error(message[EVENT_MESSAGE])
                if self.unsub:
                    self.unsub()
                    self.unsub = None
                raise ConfigEntryAuthFailed(message[EVENT_MESSAGE])
            self.logger.warning(
                "Error message from %s: %s", self.title, message[EVENT_DATA]
            )

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
                "Websocket connection closed for %s. Will retry: %s",
                self.title,
                exception,
            )
        except ConnectionErrorException as exception:
            self.last_update_success = False
            self.update_listeners()
            self.logger.warning(
                "Connection error occurred for %s. Will retry: %s",
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
            raise ConfigEntryNotReady() from exception

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
