"""DataUpdateCoordinator for System Bridge."""

from __future__ import annotations

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
from systembridgemodels.modules import (
    GetData,
    Module,
    ModulesData,
    RegisterDataListener,
)

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

        self.websocket_client = WebSocketClient(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
        )

        self._host = entry.data[CONF_HOST]

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

        self.data = SystemBridgeData()

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
        modules: list[Module],
    ) -> ModulesData:
        """Get data from WebSocket."""
        if not self.websocket_client.connected:
            await self.websocket_client.connect()

        modules_data = await self.websocket_client.get_data(GetData(modules=modules))

        # Merge new data with existing data
        for module in MODULES:
            if hasattr(modules_data, module):
                self.logger.debug("[async_get_data] Set new data for: %s", module)
                setattr(self.data, module, getattr(modules_data, module))

        return modules_data

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
        self.logger.debug("[async_handle_module] Set new data for: %s", module_name)
        setattr(self.data, module_name, module)
        self.async_set_updated_data(self.data)

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
                "[_listen_for_data] Websocket connection closed for %s. Will retry: %s",
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
                "[_listen_for_data] Connection error occurred for %s. Will retry: %s",
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
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={
                    "title": self.title,
                    "host": self._host,
                },
            ) from exception
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
            await self.websocket_client.close(True)

        # Clean disconnect WebSocket on Home Assistant shutdown
        self.unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, close_websocket
        )

    async def _async_update_data(self) -> SystemBridgeData:
        """Update System Bridge data from WebSocket."""
        self.logger.debug(
            "[_async_update_data] WebSocket Connected: %s",
            self.websocket_client.connected,
        )
        if not self.websocket_client.connected:
            await self._setup_websocket()

        self.logger.debug("[_async_update_data] Done")

        return self.data
