"""DataUpdateCoordinator for System Bridge."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

import async_timeout
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from systembridgeconnector.const import (
    EVENT_DATA,
    EVENT_MODULE,
    EVENT_SUBTYPE,
    EVENT_TYPE,
    SUBTYPE_LISTENER_ALREADY_REGISTERED,
    TYPE_DATA_UPDATE,
    TYPE_ERROR,
)
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.battery import Battery
from systembridgeconnector.models.cpu import Cpu
from systembridgeconnector.models.disk import Disk
from systembridgeconnector.models.display import Display
from systembridgeconnector.models.generic import Generic
from systembridgeconnector.models.gpu import Gpu
from systembridgeconnector.models.memory import Memory
from systembridgeconnector.models.system import System
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MODULES


class SystemBridgeCoordinatorData(BaseModel):
    """System Bridge Coordianator Data."""

    battery: Battery = None
    cpu: Cpu = None
    disk: Disk = None
    display: Display = None
    gpu: Gpu = None
    memory: Memory = None
    system: System = None


class SystemBridgeDataUpdateCoordinator(
    DataUpdateCoordinator[SystemBridgeCoordinatorData]
):
    """Class to manage fetching System Bridge data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        LOGGER: logging.Logger,
        *,
        entry: ConfigEntry,
        websocket_client: WebSocketClient,
    ) -> None:
        """Initialize global System Bridge data updater."""
        self.title = entry.title
        self.unsub: Callable | None = None

        self.systembridge_data = SystemBridgeCoordinatorData()
        self.websocket_client = websocket_client

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    def update_listeners(self) -> None:
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def async_handle_message(self, message: Generic) -> None:
        """Handle messages from the WebSocket."""
        # No need to update anything, as everything is updated in the caller
        self.logger.debug("New message from %s: %s", self.title, message[EVENT_TYPE])
        if message[EVENT_TYPE] == TYPE_DATA_UPDATE:
            self.logger.debug("Set new data for: %s", message[EVENT_MODULE])
            if message[EVENT_MODULE] == "battery":
                self.systembridge_data.battery = Battery(**message[EVENT_DATA])
            elif message[EVENT_MODULE] == "cpu":
                self.systembridge_data.cpu = Cpu(**message[EVENT_DATA])
            elif message[EVENT_MODULE] == "disk":
                self.systembridge_data.disk = Disk(**message[EVENT_DATA])
            elif message[EVENT_MODULE] == "display":
                self.systembridge_data.display = Display(**message[EVENT_DATA])
            elif message[EVENT_MODULE] == "gpu":
                self.systembridge_data.gpu = Gpu(**message[EVENT_DATA])
            elif message[EVENT_MODULE] == "memory":
                self.systembridge_data.memory = Memory(**message[EVENT_DATA])
            elif message[EVENT_MODULE] == "system":
                self.systembridge_data.system = System(**message[EVENT_DATA])

            self.async_set_updated_data(self.systembridge_data)
        elif message[EVENT_TYPE] == TYPE_ERROR:
            if message[EVENT_SUBTYPE] == SUBTYPE_LISTENER_ALREADY_REGISTERED:
                self.logger.debug(message)
            else:
                self.logger.warning("Error message from %s: %s", self.title, message)

    async def _listen_for_events(self) -> None:
        """Listen for events from the WebSocket."""

        try:
            await self.websocket_client.register_data_listener(MODULES)
            await self.websocket_client.listen_for_messages(
                callback=self.async_handle_message
            )
        except AuthenticationException as exception:
            self.last_update_success = False
            self.logger.error("Authentication failed for %s: %s", self.title, exception)
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.update_listeners()
        except (ConnectionClosedException, ConnectionResetError) as exception:
            self.logger.info(
                "Websocket connection closed for %s. Will retry: %s",
                self.title,
                exception,
            )
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.update_listeners()
        except ConnectionErrorException as exception:
            self.logger.warning(
                "Connection error occurred for %s. Will retry: %s",
                self.title,
                exception,
            )
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.update_listeners()

    async def _setup_websocket(self) -> None:
        """Use WebSocket for updates."""

        if not self.websocket_client.connected:
            try:
                async with async_timeout.timeout(20):
                    await self.websocket_client.connect(
                        session=async_get_clientsession(self.hass),
                    )
            except AuthenticationException as exception:
                self.last_update_success = False
                self.logger.error(
                    "Authentication failed for %s: %s", self.title, exception
                )
                if self.unsub:
                    self.unsub()
                    self.unsub = None
                self.last_update_success = False
                self.update_listeners()
            except ConnectionErrorException as exception:
                self.logger.warning(
                    "Connection error occurred for %s. Will retry: %s",
                    self.title,
                    exception,
                )
                self.last_update_success = False
                self.update_listeners()
            except asyncio.TimeoutError as exception:
                self.logger.warning(
                    "Timed out waiting for %s. Will retry: %s",
                    self.title,
                    exception,
                )
                self.last_update_success = False
                self.update_listeners()

        async def close_websocket(_) -> None:
            """Close WebSocket connection."""
            await self.websocket_client.close()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_websocket
        )

    async def _async_update_data(self) -> SystemBridgeCoordinatorData:
        """Update System Bridge data from WebSocket."""
        self.logger.debug(
            "_async_update_data - WebSocket Connected: %s",
            self.websocket_client.connected,
        )
        if not self.websocket_client.connected:
            await self._setup_websocket()

        self.hass.async_create_task(self._listen_for_events())

        return self.systembridge_data
