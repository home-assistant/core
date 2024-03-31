"""DataUpdateCoordinator for System Bridge."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.websocket_client import WebSocketClient
from systembridgemodels.media_directories import MediaDirectory
from systembridgemodels.media_files import MediaFile, MediaFiles
from systembridgemodels.media_get_file import MediaGetFile
from systembridgemodels.media_get_files import MediaGetFiles
from systembridgemodels.modules import GetData, RegisterDataListener
from systembridgemodels.response import Response

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MODULES
from .data import SystemBridgeData


class SystemBridgeDataUpdateCoordinator(DataUpdateCoordinator[SystemBridgeData]):
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

        self.systembridge_data = SystemBridgeData()
        self.websocket_client = WebSocketClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
        )

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @property
    def is_ready(self) -> bool:
        """Return if the data is ready."""
        if self.data is None:
            return False
        for module in MODULES:
            if getattr(self.data, module) is None:
                self.logger.debug("%s - Module %s is None", self.title, module)
                return False
        return True

    async def async_get_data(
        self,
        modules: list[str],
    ) -> Response:
        """Get data from WebSocket."""
        if not self.websocket_client.connected:
            await self._setup_websocket()

        return await self.websocket_client.get_data(GetData(modules=modules))

    async def async_get_media_directories(self) -> list[MediaDirectory]:
        """Get media directories."""
        return await self.websocket_client.get_directories()

    async def async_get_media_files(
        self,
        base: str,
        path: str | None = None,
    ) -> MediaFiles:
        """Get media files."""
        return await self.websocket_client.get_files(
            MediaGetFiles(
                base=base,
                path=path,
            )
        )

    async def async_get_media_file(
        self,
        base: str,
        path: str,
    ) -> MediaFile | None:
        """Get media file."""
        return await self.websocket_client.get_file(
            MediaGetFile(
                base=base,
                path=path,
            )
        )

    async def async_handle_module(
        self,
        module_name: str,
        module: Any,
    ) -> None:
        """Handle data from the WebSocket client."""
        self.logger.debug("Set new data for: %s", module_name)
        setattr(self.systembridge_data, module_name, module)
        self.async_set_updated_data(self.systembridge_data)

    async def _listen_for_data(self) -> None:
        """Listen for events from the WebSocket."""
        try:
            await self.websocket_client.listen(callback=self.async_handle_module)
        except AuthenticationException as exception:
            self.last_update_success = False
            self.logger.error(
                "Authentication failed while listening for %s: %s",
                self.title,
                exception,
            )
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.async_update_listeners()
        except (ConnectionClosedException, ConnectionResetError) as exception:
            self.logger.debug(
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
            self.logger.debug(
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
            async with asyncio.timeout(20):
                await self.websocket_client.connect()

            self.hass.async_create_background_task(
                self._listen_for_data(),
                name="System Bridge WebSocket Listener",
            )

            await self.websocket_client.register_data_listener(
                RegisterDataListener(modules=MODULES)
            )
            self.last_update_success = True
            self.async_update_listeners()
        except AuthenticationException as exception:
            self.logger.error(
                "Authentication failed at setup for %s: %s", self.title, exception
            )
            if self.unsub:
                self.unsub()
                self.unsub = None
            self.last_update_success = False
            self.async_update_listeners()
            raise ConfigEntryAuthFailed from exception
        except ConnectionErrorException as exception:
            self.logger.warning(
                "Connection error occurred for %s. Will retry: %s",
                self.title,
                exception,
            )
            self.last_update_success = False
            self.async_update_listeners()
        except TimeoutError as exception:
            self.logger.warning(
                "Timed out waiting for %s. Will retry: %s",
                self.title,
                exception,
            )
            self.last_update_success = False
            self.async_update_listeners()

        async def close_websocket(_) -> None:
            """Close WebSocket connection."""
            await self.websocket_client.close()

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_websocket
        )

    async def _async_update_data(self) -> SystemBridgeData:
        """Update System Bridge data from WebSocket."""
        self.logger.debug(
            "_async_update_data - WebSocket Connected: %s",
            self.websocket_client.connected,
        )
        if not self.websocket_client.connected:
            await self._setup_websocket()

        self.logger.debug("_async_update_data done")

        return self.systembridge_data
