"""DataUpdateCoordinator for System Bridge."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

import async_timeout
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.battery import Battery
from systembridgeconnector.models.cpu import Cpu
from systembridgeconnector.models.disk import Disk
from systembridgeconnector.models.display import Display
from systembridgeconnector.models.gpu import Gpu
from systembridgeconnector.models.memory import Memory
from systembridgeconnector.models.system import System
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
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
    ) -> None:
        """Initialize global System Bridge data updater."""
        self.title = entry.title
        self.unsub: Callable | None = None

        self.systembridge_data = SystemBridgeCoordinatorData()
        self.websocket_client = WebSocketClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_API_KEY],
        )

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    async def async_get_data(
        self,
        modules: list[str],
    ) -> None:
        """Get data from WebSocket."""
        if not self.websocket_client.connected:
            await self._setup_websocket()

        await self.websocket_client.get_data(modules)

    async def async_handle_module(
        self,
        module_name: str,
        module,
    ) -> None:
        """Handle data from the WebSocket client."""
        self.logger.debug("Set new data for: %s", module_name)
        setattr(self.systembridge_data, module_name, module)
        self.async_set_updated_data(self.systembridge_data)

    async def _listen_for_data(self) -> None:
        """Listen for events from the WebSocket."""

        try:
            await self.websocket_client.register_data_listener(MODULES)
            await self.websocket_client.listen(callback=self.async_handle_module)
        except AuthenticationException as exception:
            self.last_update_success = False
            self.logger.error("Authentication failed for %s: %s", self.title, exception)
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.async_update_listeners()
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
            self.async_update_listeners()
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
            self.async_update_listeners()

    async def _setup_websocket(self) -> None:
        """Use WebSocket for updates."""
        try:
            async with async_timeout.timeout(20):
                await self.websocket_client.connect(
                    session=async_get_clientsession(self.hass),
                )
        except AuthenticationException as exception:
            self.last_update_success = False
            self.logger.error("Authentication failed for %s: %s", self.title, exception)
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.async_update_listeners()
        except ConnectionErrorException as exception:
            self.logger.warning(
                "Connection error occurred for %s. Will retry: %s",
                self.title,
                exception,
            )
            self.last_update_success = False
            self.async_update_listeners()
        except asyncio.TimeoutError as exception:
            self.logger.warning(
                "Timed out waiting for %s. Will retry: %s",
                self.title,
                exception,
            )
            self.last_update_success = False
            self.async_update_listeners()

        self.hass.async_create_task(self._listen_for_data())
        self.last_update_success = True
        self.async_update_listeners()

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

        self.logger.debug("_async_update_data done")

        return self.systembridge_data
