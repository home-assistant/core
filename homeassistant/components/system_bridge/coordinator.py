"""DataUpdateCoordinator for System Bridge."""

import asyncio
from asyncio import Task
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any, override

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.modules import (
    GetData,
    Module,
    ModulesData,
    RegisterDataListener,
)
from systembridgeconnector.models.notification import NotificationEvent
from systembridgeconnector.models.system_control import PowerState, PowerStateEvent
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, GET_DATA_WAIT_TIMEOUT, MODULES, SIGNAL_NOTIFICATION_EVENT
from .data import SystemBridgeData

type SystemBridgeConfigEntry = ConfigEntry[SystemBridgeDataUpdateCoordinator]

UPDATE_INTERVAL = timedelta(seconds=30)
MAX_UPDATE_INTERVAL = timedelta(minutes=2)


class SystemBridgeDataUpdateCoordinator(DataUpdateCoordinator[SystemBridgeData]):
    """Class to manage fetching System Bridge data from single endpoint."""

    config_entry: SystemBridgeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        LOGGER: logging.Logger,
        *,
        entry: SystemBridgeConfigEntry,
    ) -> None:
        """Initialize global System Bridge data updater."""
        self.title = entry.title
        self.unsub: Callable | None = None

        self.listen_task: Task | None = None
        self._register_task: Task | None = None
        self.websocket_client = WebSocketClient(
            api_host=entry.data[CONF_HOST],
            api_port=entry.data[CONF_PORT],
            token=entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
            can_close_session=False,
        )

        self._host = entry.data[CONF_HOST]
        self._reconnect_delay = UPDATE_INTERVAL
        self._unavailable_logged = False
        self._reconnect_after: datetime | None = None

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.data = SystemBridgeData()

    async def check_websocket_connected(self) -> None:
        """Check if WebSocket is connected."""
        self.logger.debug(
            "[check_websocket_connected] WebSocket connected: %s",
            self.websocket_client.connected,
        )

        if not self.websocket_client.connected:
            try:
                await self.websocket_client.connect()
            except ConnectionErrorException as exception:
                self.logger.debug(
                    "[check_websocket_connected] Connection error occurred for %s: %s",
                    self.title,
                    exception,
                )
                await self.clean_disconnect()

    async def close_websocket(self, _: Event) -> None:
        """Close WebSocket connection."""
        await self.websocket_client.close()
        if self.listen_task is not None:
            self.listen_task.cancel(
                msg="WebSocket closed on Home Assistant shutdown",
            )

    @override
    async def async_shutdown(self) -> None:
        """Stop listening and close the WebSocket on unload or failed setup."""
        await super().async_shutdown()
        if self.unsub:
            self.unsub()
            self.unsub = None
        await self.websocket_client.close()
        if self.listen_task is not None:
            self.listen_task.cancel(msg="Config entry unloaded")

    async def clean_disconnect(self) -> None:
        """Clean disconnect WebSocket."""
        if self.unsub:
            self.unsub()
            self.unsub = None
        # Setup failures are reported through ConfigEntryNotReady instead
        if (
            not self._unavailable_logged
            and self.config_entry.state is ConfigEntryState.LOADED
        ):
            self.logger.info("%s is unavailable", self.title)
            self._unavailable_logged = True
        self.last_update_success = False
        self.async_update_listeners()
        if self.listen_task is not None:
            self.listen_task.cancel(
                msg="WebSocket disconnected",
            )
        if self._register_task is not None:
            self._register_task.cancel()

    async def async_get_data(
        self,
        modules: list[Module],
    ) -> ModulesData:
        """Get data from WebSocket."""
        await self.check_websocket_connected()

        modules_data = await self.websocket_client.get_data(
            GetData(modules=modules),
            timeout=GET_DATA_WAIT_TIMEOUT,
        )

        # Merge new data with existing data
        for module in modules:
            self.logger.debug("[async_get_data] Set new data for: %s", module)
            setattr(self.data, module, getattr(modules_data, module))

        return modules_data

    async def async_handle_module(
        self,
        module_name: str,
        module: Any,
    ) -> None:
        """Handle data from the WebSocket client."""
        self.logger.debug("[async_handle_module] Set new data for: %s", module_name)
        setattr(self.data, module_name, module)
        self.async_set_updated_data(self.data)

    async def async_handle_power_state(self, event: PowerStateEvent) -> None:
        """Go unavailable as soon as the host says it's sleeping or shutting down."""
        if event.state is PowerState.RESUMED:
            return
        if (
            not self._unavailable_logged
            and self.config_entry.state is ConfigEntryState.LOADED
        ):
            self.logger.info("%s is unavailable: %s", self.title, event.state)
            self._unavailable_logged = True
        # Reconnecting before the host has gone would mark it available again
        self._reconnect_after = dt_util.utcnow() + UPDATE_INTERVAL
        await self.clean_disconnect()
        # A sleeping host can leave the socket open, which would stop reconnects.
        # Close it in its own task, as clean_disconnect cancels this listener
        self.config_entry.async_create_background_task(
            self.hass,
            self.websocket_client.close(),
            "System Bridge WebSocket close",
        )

    @callback
    def async_reconnect_now(self) -> None:
        """Reconnect without waiting out the backoff, as the host is back."""
        self._reconnect_delay = UPDATE_INTERVAL
        self._reconnect_after = None
        self.config_entry.async_create_background_task(
            self.hass,
            self.async_request_refresh(),
            "System Bridge reconnect",
        )

    async def async_handle_notification_event(self, event: NotificationEvent) -> None:
        """Pass a click on, or close of, a notification to the event entity."""
        async_dispatcher_send(
            self.hass,
            SIGNAL_NOTIFICATION_EVENT.format(self.config_entry.entry_id),
            event,
        )

    async def _listen_for_data(self) -> None:
        """Listen for events from the WebSocket."""
        try:
            await self.websocket_client.listen(
                callback=self.async_handle_module,
                notification_event_callback=self.async_handle_notification_event,
                power_state_callback=self.async_handle_power_state,
            )
        except AuthenticationException as exception:
            self.logger.error(
                "Authentication failed while listening for %s: %s",
                self.title,
                exception,
            )
            await self.clean_disconnect()
        except (ConnectionClosedException, ConnectionResetError) as exception:
            self.logger.debug(
                "[_listen_for_data] Websocket connection closed for %s: %s",
                self.title,
                exception,
            )
            await self.clean_disconnect()
        except ConnectionErrorException as exception:
            self.logger.debug(
                "[_listen_for_data] Connection error occurred for %s: %s",
                self.title,
                exception,
            )
            await self.clean_disconnect()

    async def _register_data_listener(self) -> None:
        """Register for data, unless a disconnect cancels it first."""
        # The response arrives through the listener, so once it stops this
        # would otherwise wait for the connector's timeout
        self._register_task = self.config_entry.async_create_task(
            self.hass,
            self.websocket_client.register_data_listener(
                RegisterDataListener(modules=[*MODULES, Module.AUDIO])
            ),
            "System Bridge register data listener",
        )
        try:
            if not self._register_task.done():
                await asyncio.wait((self._register_task,))
        finally:
            self._register_task.cancel()
        if not self._register_task.cancelled():
            self._register_task.result()

    @override
    async def _async_update_data(self) -> SystemBridgeData:
        """Update System Bridge data from WebSocket."""
        if self.listen_task is None or not self.websocket_client.connected:
            if (
                self._reconnect_after is not None
                and (wait := self._reconnect_after - dt_util.utcnow()) > timedelta()
            ):
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="waiting_for_sleep",
                    translation_placeholders={"title": self.title},
                    retry_after=wait.total_seconds(),
                )
            await self.check_websocket_connected()

            self.logger.debug("Create listener task for %s", self.title)
            self.listen_task = self.hass.async_create_background_task(
                self._listen_for_data(),
                name="System Bridge WebSocket Listener",
                eager_start=False,
            )
            self.logger.debug("Listening for data from %s", self.title)

            try:
                await self._register_data_listener()
            except AuthenticationException as exception:
                await self.clean_disconnect()
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                    translation_placeholders={
                        "title": self.title,
                        "host": self._host,
                    },
                ) from exception
            except (ConnectionClosedException, ConnectionErrorException) as exception:
                await self.clean_disconnect()
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, MAX_UPDATE_INTERVAL
                )
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_failed",
                    translation_placeholders={
                        "title": self.title,
                        "host": self._host,
                    },
                    retry_after=self._reconnect_delay.total_seconds(),
                ) from exception

            # A power event can stop the listener just as registration finishes
            if self.listen_task.done() or self.listen_task.cancelling():
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, MAX_UPDATE_INTERVAL
                )
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_lost",
                    translation_placeholders={"title": self.title},
                    retry_after=self._reconnect_delay.total_seconds(),
                )

            self.logger.debug("Registered data listener for %s", self.title)
            self._reconnect_delay = UPDATE_INTERVAL
            if self._unavailable_logged:
                self.logger.info("%s is available again", self.title)
                self._unavailable_logged = False
                # Pushed data can mark the update successful before the
                # refresh ends, so the built-in recovery log isn't reliable
                self.last_update_success = True

            # Clean disconnect WebSocket on Home Assistant shutdown
            self.unsub = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self.close_websocket
            )

        self.logger.debug("[_async_update_data] Done")

        return self.data
