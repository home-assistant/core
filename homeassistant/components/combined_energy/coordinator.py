"""DataUpdateCoordinator for the PVOutput integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
from typing import Generic, TypeVar

from combined_energy import CombinedEnergy
from combined_energy.exceptions import CombinedEnergyAuthError, CombinedEnergyError
from combined_energy.helpers import ReadingsIterator
from combined_energy.models import ConnectionStatus, DeviceReadings

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONNECTIVITY_UPDATE_DELAY,
    LOG_SESSION_REFRESH_DELAY,
    LOGGER,
    READINGS_INCREMENT,
    READINGS_INITIAL_DELTA,
    READINGS_UPDATE_DELAY,
)

_T = TypeVar("_T")


class CombinedEnergyDataService(Generic[_T]):
    """Get and update the latest data."""

    coordinator: DataUpdateCoordinator[_T]

    def __init__(self, hass: HomeAssistant, api: CombinedEnergy) -> None:
        """Initialize the data service."""
        self.hass = hass
        self.api = api

        self.data: _T | None = None

    def async_setup(self) -> None:
        """Coordinator creation."""
        self.coordinator = DataUpdateCoordinator[_T](
            self.hass,
            LOGGER,
            name=str(self),
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    @abstractmethod
    def update_interval(self) -> timedelta:
        """Update interval."""

    @abstractmethod
    async def update_data(self) -> _T:
        """Update data."""

    async def async_update_data(self) -> _T:
        """Update data with error handling."""
        try:
            self.data = await self.update_data()
        except CombinedEnergyAuthError as ex:
            raise ConfigEntryAuthFailed from ex
        except CombinedEnergyError as ex:
            raise UpdateFailed("Error updating Combined Energy") from ex
        return self.data


class CombinedEnergyConnectivityDataService(
    CombinedEnergyDataService[ConnectionStatus]
):
    """Get and update the latest connectivity status data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return CONNECTIVITY_UPDATE_DELAY

    async def update_data(self) -> ConnectionStatus:
        """Update data."""
        return await self.api.communication_status()


class CombinedEnergyLogSessionService(CombinedEnergyDataService[None]):
    """Triggers a log session refresh event keep readings data flowing."""

    def async_setup(self) -> None:
        """Configure data service coordinator."""
        super().async_setup()
        self.coordinator.async_add_listener(self.update_listener)

    @staticmethod
    def update_listener() -> None:
        """Log that the session has been restarted."""
        LOGGER.info("Log session has been restarted")

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return LOG_SESSION_REFRESH_DELAY

    async def update_data(self) -> None:
        """Update data."""
        await self.api.start_log_session()


class CombinedEnergyReadingsDataService(
    CombinedEnergyDataService[dict[int, DeviceReadings]]
):
    """Get and update the latest readings data."""

    def __init__(self, hass: HomeAssistant, api: CombinedEnergy) -> None:
        """Initialize the data service."""
        super().__init__(hass, api)
        self._readings_iterator = ReadingsIterator(
            self.api,
            increment=READINGS_INCREMENT,
            initial_delta=READINGS_INITIAL_DELTA,
        )

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return READINGS_UPDATE_DELAY

    async def update_data(self) -> dict[int, DeviceReadings]:
        """Update data."""
        readings = await anext(self._readings_iterator)
        return {
            device.device_id: device
            for device in readings.devices
            if device.device_id is not None
        }
