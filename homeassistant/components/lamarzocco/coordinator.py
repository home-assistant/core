"""Coordinator for La Marzocco API."""

from __future__ import annotations

from abc import abstractmethod
from asyncio import Task
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pylamarzocco import LaMarzoccoMachine
from pylamarzocco.exceptions import (
    AuthFail,
    BluetoothConnectionFailed,
    RequestNotSuccessful,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_OFFLINE_MODE, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)
SETTINGS_UPDATE_INTERVAL = timedelta(hours=8)
SCHEDULE_UPDATE_INTERVAL = timedelta(minutes=30)
STATISTICS_UPDATE_INTERVAL = timedelta(minutes=15)
_LOGGER = logging.getLogger(__name__)


@dataclass
class LaMarzoccoRuntimeData:
    """Runtime data for La Marzocco."""

    config_coordinator: LaMarzoccoConfigUpdateCoordinator
    settings_coordinator: LaMarzoccoSettingsUpdateCoordinator
    schedule_coordinator: LaMarzoccoScheduleUpdateCoordinator
    statistics_coordinator: LaMarzoccoStatisticsUpdateCoordinator
    bluetooth_coordinator: LaMarzoccoBluetoothUpdateCoordinator | None = None


type LaMarzoccoConfigEntry = ConfigEntry[LaMarzoccoRuntimeData]


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Base class for La Marzocco coordinators."""

    _default_update_interval: timedelta | None = SCAN_INTERVAL
    _ignore_offline_mode = False
    config_entry: LaMarzoccoConfigEntry
    update_success = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LaMarzoccoConfigEntry,
        device: LaMarzoccoMachine,
    ) -> None:
        """Initialize coordinator."""
        update_interval = self._default_update_interval
        if not self._ignore_offline_mode and entry.options.get(
            CONF_OFFLINE_MODE, False
        ):
            update_interval = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.device = device
        self._websocket_task: Task | None = None

    @property
    def websocket_terminated(self) -> bool:
        """Return True if the websocket task is terminated or not running."""
        if self._websocket_task is None:
            return True
        return self._websocket_task.done()

    async def __handle_internal_update(
        self, func: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Handle update with error handling."""
        try:
            await func()
        except AuthFail as ex:
            _LOGGER.debug("Authentication failed", exc_info=True)
            self.update_success = False
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            self.update_success = False
            # if no bluetooth coordinator, this is a fatal error
            # otherwise, bluetooth may still work
            if not self.device.bluetooth_client_available:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="api_error"
                ) from ex
        except BluetoothConnectionFailed as err:
            self.update_success = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="bluetooth_connection_failed",
            ) from err
        else:
            self.update_success = True
        _LOGGER.debug("Current status: %s", self.device.dashboard.to_dict())

    async def _async_setup(self) -> None:
        """Set up coordinator."""
        await self.__handle_internal_update(self._internal_async_setup)

    async def _async_update_data(self) -> None:
        """Do the data update."""
        await self.__handle_internal_update(self._internal_async_update_data)

    async def _internal_async_setup(self) -> None:
        """Actual setup logic."""

    @abstractmethod
    async def _internal_async_update_data(self) -> None:
        """Actual data update logic."""


class LaMarzoccoConfigUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Class to handle fetching data from the La Marzocco API centrally."""

    async def _internal_async_setup(self) -> None:
        """Set up the coordinator."""
        await self.device.ensure_token_valid()
        await self.device.get_dashboard()
        _LOGGER.debug("Current status: %s", self.device.dashboard.to_dict())

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        # ensure token stays valid; does nothing if token is still valid
        await self.device.ensure_token_valid()

        # Only skip websocket reconnection if it's currently connected and the task is still running
        if self.device.websocket.connected and not self.websocket_terminated:
            return

        self._websocket_task = self.config_entry.async_create_background_task(
            hass=self.hass,
            target=self.connect_websocket(),
            name="lm_websocket_task",
        )

        async def websocket_close(_: Any | None = None) -> None:
            await self.device.websocket.disconnect()

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, websocket_close)
        )
        self.config_entry.async_on_unload(websocket_close)

    async def connect_websocket(self) -> None:
        """Connect to the websocket."""

        _LOGGER.debug("Init WebSocket in background task")

        self.async_update_listeners()

        @callback
        def update_callback(_: Any | None = None) -> None:
            _LOGGER.debug("Current status: %s", self.device.dashboard.to_dict())
            self.async_set_updated_data(None)

        await self.device.connect_dashboard_websocket(
            update_callback=update_callback,
            connect_callback=self.async_update_listeners,
            disconnect_callback=self.async_update_listeners,
        )

        self.async_update_listeners()


class LaMarzoccoSettingsUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Coordinator for La Marzocco settings."""

    _default_update_interval = SETTINGS_UPDATE_INTERVAL

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.device.get_settings()
        _LOGGER.debug("Current settings: %s", self.device.settings.to_dict())


class LaMarzoccoScheduleUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Coordinator for La Marzocco schedule."""

    _default_update_interval = SCHEDULE_UPDATE_INTERVAL

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.device.get_schedule()
        _LOGGER.debug("Current schedule: %s", self.device.schedule.to_dict())


class LaMarzoccoStatisticsUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Coordinator for La Marzocco statistics."""

    _default_update_interval = STATISTICS_UPDATE_INTERVAL

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.device.get_coffee_and_flush_counter()
        _LOGGER.debug("Current statistics: %s", self.device.statistics.to_dict())


class LaMarzoccoBluetoothUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Class to handle fetching data from the La Marzocco Bluetooth API centrally."""

    _ignore_offline_mode = True

    async def _internal_async_setup(self) -> None:
        """Initial setup for Bluetooth coordinator."""
        await self.device.get_model_info_from_bluetooth()

    async def _internal_async_update_data(self) -> None:
        """Fetch data from Bluetooth endpoint."""
        # if the websocket is connected and the machine is connected to the cloud
        # skip bluetooth update, because we get push updates
        if self.device.websocket.connected and self.device.dashboard.connected:
            return
        await self.device.get_dashboard_from_bluetooth()
