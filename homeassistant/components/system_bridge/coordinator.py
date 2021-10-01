"""DataUpdateCoordinator for System Bridge."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

from systembridge import Bridge
from systembridge.exceptions import (
    BridgeAuthenticationException,
    BridgeConnectionClosedException,
    BridgeException,
)
from systembridge.objects.events import Event

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BRIDGE_CONNECTION_ERRORS, DOMAIN


class SystemBridgeDataUpdateCoordinator(DataUpdateCoordinator[Bridge]):
    """Class to manage fetching System Bridge data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        bridge: Bridge,
        LOGGER: logging.Logger,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global System Bridge data updater."""
        self.bridge = bridge
        self.title = entry.title
        self.host = entry.data[CONF_HOST]
        self.unsub: Callable | None = None

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def async_handle_event(self, event: Event):
        """Handle System Bridge events from the WebSocket."""
        # No need to update anything, as everything is updated in the caller
        self.logger.debug(
            "New event from %s (%s): %s", self.title, self.host, event.name
        )
        self.async_set_updated_data(self.bridge)

    async def _listen_for_events(self) -> None:
        """Listen for events from the WebSocket."""
        try:
            await self.bridge.async_send_event(
                "get-data",
                [
                    "battery",
                    "cpu",
                    "filesystem",
                    "graphics",
                    "memory",
                    "network",
                    "os",
                    "processes",
                    "system",
                ],
            )
            await self.bridge.listen_for_events(callback=self.async_handle_event)
        except BridgeConnectionClosedException as exception:
            self.last_update_success = False
            self.logger.info(
                "Websocket Connection Closed for %s (%s). Will retry: %s",
                self.title,
                self.host,
                exception,
            )
        except BridgeException as exception:
            self.last_update_success = False
            self.update_listeners()
            self.logger.warning(
                "Exception occurred for %s (%s). Will retry: %s",
                self.title,
                self.host,
                exception,
            )

    async def _setup_websocket(self) -> None:
        """Use WebSocket for updates."""

        try:
            self.logger.debug(
                "Connecting to ws://%s:%s",
                self.host,
                self.bridge.information.websocketPort,
            )
            await self.bridge.async_connect_websocket(
                self.host, self.bridge.information.websocketPort
            )
        except BridgeAuthenticationException as exception:
            if self.unsub:
                self.unsub()
                self.unsub = None
            raise ConfigEntryAuthFailed() from exception
        except (*BRIDGE_CONNECTION_ERRORS, ConnectionRefusedError) as exception:
            if self.unsub:
                self.unsub()
                self.unsub = None
            raise UpdateFailed(
                f"Could not connect to {self.title} ({self.host})."
            ) from exception
        asyncio.create_task(self._listen_for_events())

        async def close_websocket(_) -> None:
            """Close WebSocket connection."""
            await self.bridge.async_close_websocket()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_websocket
        )

    async def _async_update_data(self) -> Bridge:
        """Update System Bridge data from WebSocket."""
        self.logger.debug(
            "_async_update_data - WebSocket Connected: %s",
            self.bridge.websocket_connected,
        )
        if not self.bridge.websocket_connected:
            await self._setup_websocket()

        return self.bridge
