"""DataUpdateCoordinator for the PVOutput integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
from typing import TypeVar

from combined_energy import CombinedEnergy
from combined_energy.exceptions import CombinedEnergyAuthError, CombinedEnergyError
from combined_energy.helpers import ReadingsIterator
from combined_energy.models import DeviceReadings

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    LOG_SESSION_REFRESH_DELAY,
    LOGGER,
    READINGS_INCREMENT,
    READINGS_INITIAL_DELTA,
    READINGS_UPDATE_DELAY,
)

_T = TypeVar("_T")


class _CombinedEnergyCoordinator(DataUpdateCoordinator[_T]):
    """Get and update the latest data."""

    def __init__(
        self, hass: HomeAssistant, api: CombinedEnergy, update_interval: timedelta
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=type(self).__name__,
            update_interval=update_interval,
        )
        self.api = api

    @abstractmethod
    async def _update_data(self) -> _T:
        """Update data."""

    async def _async_update_data(self) -> _T:
        """Update data with error handling."""
        try:
            return await self._update_data()
        except CombinedEnergyAuthError as ex:
            raise ConfigEntryAuthFailed from ex
        except CombinedEnergyError as ex:
            raise UpdateFailed("Error updating Combined Energy") from ex


class CombinedEnergyLogSessionCoordinator(_CombinedEnergyCoordinator[None]):
    """Triggers a log session refresh event keep readings data flowing.

    If this is not done periodically, the log session will expire and
    readings data stops being returned.
    """

    def __init__(self, hass: HomeAssistant, api: CombinedEnergy) -> None:
        """Initialize coordinator."""
        super().__init__(hass, api, LOG_SESSION_REFRESH_DELAY)
        self.async_add_listener(self.update_listener)

    @staticmethod
    def update_listener() -> None:
        """Log that the session has been restarted."""
        LOGGER.debug("Log session has been restarted")

    async def _update_data(self) -> None:
        """Update data."""
        await self.api.start_log_session()


class CombinedEnergyReadingsCoordinator(
    _CombinedEnergyCoordinator[dict[int, DeviceReadings]]
):
    """Get and update the latest readings data."""

    def __init__(self, hass: HomeAssistant, api: CombinedEnergy) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, api, READINGS_UPDATE_DELAY)
        self._readings_iterator = ReadingsIterator(
            self.api,
            increment=READINGS_INCREMENT,
            initial_delta=READINGS_INITIAL_DELTA,
        )

    async def _update_data(self) -> dict[int, DeviceReadings]:
        """Update data."""
        readings = await anext(self._readings_iterator)
        return {
            device.device_id: device
            for device in readings.devices
            if device.device_id is not None
        }
