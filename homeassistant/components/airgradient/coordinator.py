"""Define an object to manage fetching AirGradient data."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from airgradient import AirGradientClient, AirGradientError, Config, Measures

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

if TYPE_CHECKING:
    from . import AirGradientConfigEntry


class AirGradientCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Class to manage fetching AirGradient data."""

    config_entry: AirGradientConfigEntry

    def __init__(self, hass: HomeAssistant, client: AirGradientClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"AirGradient {client.host}",
            update_interval=timedelta(minutes=1),
        )
        self.client = client
        assert self.config_entry.unique_id
        self.serial_number = self.config_entry.unique_id

    async def _async_update_data(self) -> _DataT:
        try:
            return await self._update_data()
        except AirGradientError as error:
            raise UpdateFailed(error) from error

    async def _update_data(self) -> _DataT:
        raise NotImplementedError


class AirGradientMeasurementCoordinator(AirGradientCoordinator[Measures]):
    """Class to manage fetching AirGradient data."""

    async def _update_data(self) -> Measures:
        return await self.client.get_current_measures()


class AirGradientConfigCoordinator(AirGradientCoordinator[Config]):
    """Class to manage fetching AirGradient data."""

    async def _update_data(self) -> Config:
        return await self.client.get_config()
