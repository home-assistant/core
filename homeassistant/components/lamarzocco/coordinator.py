"""Coordinator for La Marzocco API."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pylamarzocco.clients.local import LaMarzoccoLocalClient
from pylamarzocco.devices.machine import LaMarzoccoMachine
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
FIRMWARE_UPDATE_INTERVAL = timedelta(hours=1)
STATISTICS_UPDATE_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


@dataclass
class LaMarzoccoRuntimeData:
    """Runtime data for La Marzocco."""

    config_coordinator: LaMarzoccoConfigUpdateCoordinator
    firmware_coordinator: LaMarzoccoFirmwareUpdateCoordinator
    statistics_coordinator: LaMarzoccoStatisticsUpdateCoordinator


type LaMarzoccoConfigEntry = ConfigEntry[LaMarzoccoRuntimeData]


class LaMarzoccoUpdateCoordinator(DataUpdateCoordinator[None]):
    """Base class for La Marzocco coordinators."""

    _default_update_interval = SCAN_INTERVAL
    config_entry: LaMarzoccoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LaMarzoccoConfigEntry,
        device: LaMarzoccoMachine,
        local_client: LaMarzoccoLocalClient | None = None,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._default_update_interval,
        )
        self.device = device
        self.local_connection_configured = local_client is not None
        self._local_client = local_client
        self.new_device_callback: list[Callable] = []

    async def _async_update_data(self) -> None:
        """Do the data update."""
        try:
            await self._internal_async_update_data()
        except AuthFail as ex:
            _LOGGER.debug("Authentication failed", exc_info=True)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from ex

    @abstractmethod
    async def _internal_async_update_data(self) -> None:
        """Actual data update logic."""


class LaMarzoccoConfigUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Class to handle fetching data from the La Marzocco API centrally."""

    _scale_address: str | None = None

    async def _async_connect_websocket(self) -> None:
        """Set up the coordinator."""
        if self._local_client is not None and (
            self._local_client.websocket is None or self._local_client.websocket.closed
        ):
            _LOGGER.debug("Init WebSocket in background task")

            self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.device.websocket_connect(
                    notify_callback=lambda: self.async_set_updated_data(None)
                ),
                name="lm_websocket_task",
            )

            async def websocket_close(_: Any | None = None) -> None:
                if (
                    self._local_client is not None
                    and self._local_client.websocket is not None
                    and not self._local_client.websocket.closed
                ):
                    await self._local_client.websocket.close()

            self.config_entry.async_on_unload(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, websocket_close
                )
            )
            self.config_entry.async_on_unload(websocket_close)

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.device.get_config()
        _LOGGER.debug("Current status: %s", str(self.device.config))
        await self._async_connect_websocket()
        self._async_add_remove_scale()

    @callback
    def _async_add_remove_scale(self) -> None:
        """Add or remove a scale when added or removed."""
        if self.device.config.scale and not self._scale_address:
            self._scale_address = self.device.config.scale.address
            for scale_callback in self.new_device_callback:
                scale_callback()
        elif not self.device.config.scale and self._scale_address:
            device_registry = dr.async_get(self.hass)
            if device := device_registry.async_get_device(
                identifiers={(DOMAIN, self._scale_address)}
            ):
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )
            self._scale_address = None


class LaMarzoccoFirmwareUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Coordinator for La Marzocco firmware."""

    _default_update_interval = FIRMWARE_UPDATE_INTERVAL

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.device.get_firmware()
        _LOGGER.debug("Current firmware: %s", str(self.device.firmware))


class LaMarzoccoStatisticsUpdateCoordinator(LaMarzoccoUpdateCoordinator):
    """Coordinator for La Marzocco statistics."""

    _default_update_interval = STATISTICS_UPDATE_INTERVAL

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.device.get_statistics()
        _LOGGER.debug("Current statistics: %s", str(self.device.statistics))
