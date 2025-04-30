"""Coordinator for La Marzocco API."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pylamarzocco import LaMarzoccoMachine
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=15)
SETTINGS_UPDATE_INTERVAL = timedelta(hours=1)
SCHEDULE_UPDATE_INTERVAL = timedelta(minutes=5)
STATISTICS_UPDATE_INTERVAL = timedelta(minutes=15)
_LOGGER = logging.getLogger(__name__)


@dataclass
class LaMarzoccoRuntimeData:
    """Runtime data for La Marzocco."""

    config_coordinator: LaMarzoccoConfigUpdateCoordinator
    settings_coordinator: LaMarzoccoSettingsUpdateCoordinator
    schedule_coordinator: LaMarzoccoScheduleUpdateCoordinator
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

    async def _internal_async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        if self.device.websocket.connected:
            return
        await self.device.get_dashboard()
        _LOGGER.debug("Current status: %s", self.device.dashboard.to_dict())

        _LOGGER.debug("Init WebSocket in background task")

        self.config_entry.async_create_background_task(
            hass=self.hass,
            target=self.device.connect_dashboard_websocket(
                update_callback=lambda _: self.async_set_updated_data(None)
            ),
            name="lm_websocket_task",
        )

        async def websocket_close(_: Any | None = None) -> None:
            if self.device.websocket.connected:
                await self.device.websocket.disconnect()

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, websocket_close)
        )
        self.config_entry.async_on_unload(websocket_close)


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
