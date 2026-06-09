"""Support for Anova Coordinators."""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging

from anova_wifi import (
    AnovaApi,
    APCUpdate,
    APCWifiDevice,
    InvalidLogin,
    NoDevicesFound,
    WebsocketFailure,
)
from anova_wifi.exceptions import LoginUnreachable

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RECONNECT_RETRY_DELAY = 60


@dataclass
class AnovaData:
    """Data for the Anova integration."""

    api_jwt: str
    coordinators: list[AnovaCoordinator]
    api: AnovaApi
    reconnect_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


type AnovaConfigEntry = ConfigEntry[AnovaData]


class AnovaCoordinator(DataUpdateCoordinator[APCUpdate | None]):
    """Anova custom coordinator."""

    config_entry: AnovaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AnovaConfigEntry,
        anova_device: APCWifiDevice,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name="Anova Precision Cooker",
            logger=_LOGGER,
            update_interval=timedelta(seconds=RECONNECT_RETRY_DELAY),
        )
        self.device_unique_id = anova_device.cooker_id
        self.anova_device = anova_device
        self.anova_device.set_update_listener(self.async_set_updated_data)
        self.device_info: DeviceInfo | None = None

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_unique_id)},
            name="Anova Precision Cooker",
            manufacturer="Anova",
            model="Precision Cooker",
        )
        self.sensor_data_set: bool = False

    @callback
    def async_start_disconnect_listener(self) -> None:
        """Register a done callback on the websocket listener to detect connection drops."""
        ws_handler = self.config_entry.runtime_data.api.websocket_handler
        if ws_handler is None or ws_handler._message_listener is None:  # noqa: SLF001
            return

        @callback
        def _on_done(task: asyncio.Future[None]) -> None:
            if task.cancelled():
                return
            if self.config_entry.state is not ConfigEntryState.LOADED:
                return
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                "anova_websocket_reconnect",
            )

        ws_handler._message_listener.add_done_callback(_on_done)  # noqa: SLF001

    async def _async_update_data(self) -> APCUpdate | None:
        """Reconnect the websocket if it has dropped; return current push data."""
        ws_handler = self.config_entry.runtime_data.api.websocket_handler
        if ws_handler is not None:
            listener = ws_handler._message_listener  # noqa: SLF001
            if listener is not None and not listener.done():
                return self.data

        async with self.config_entry.runtime_data.reconnect_lock:
            ws_handler = self.config_entry.runtime_data.api.websocket_handler
            if ws_handler is not None:
                listener = ws_handler._message_listener  # noqa: SLF001
                if listener is not None and not listener.done():
                    return self.data
            await self._async_reconnect()

        return self.data

    async def _async_reconnect(self) -> None:
        """Reconnect the Anova websocket and re-wire all device coordinators."""
        api = self.config_entry.runtime_data.api
        _LOGGER.warning("Anova websocket connection lost, attempting to reconnect")
        try:
            await api.create_websocket()
        except WebsocketFailure:
            try:
                await api.authenticate()
            except InvalidLogin as err:
                _LOGGER.error("Anova re-authentication failed: %s", err)
                raise UpdateFailed(str(err)) from err
            except LoginUnreachable as err:
                _LOGGER.warning("Failed to re-authenticate with Anova: %s", err)
                raise UpdateFailed(str(err)) from err
            try:
                await api.create_websocket()
            except (NoDevicesFound, WebsocketFailure) as err:
                _LOGGER.warning("Failed to reconnect to Anova websocket: %s", err)
                raise UpdateFailed(str(err)) from err
        except NoDevicesFound as err:
            _LOGGER.warning("Failed to reconnect to Anova websocket: %s", err)
            raise UpdateFailed(str(err)) from err

        ws_handler = api.websocket_handler
        if ws_handler is None:
            return

        for coordinator in self.config_entry.runtime_data.coordinators:
            device = ws_handler.devices.get(coordinator.device_unique_id)
            if device is not None:
                coordinator.anova_device = device
                device.set_update_listener(coordinator.async_set_updated_data)

        self.async_start_disconnect_listener()
