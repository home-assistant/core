"""Coordinator for radiotherm."""
from __future__ import annotations

from datetime import timedelta
import logging
from socket import timeout

from radiotherm.validate import RadiothermTstatError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .data import RadioThermInitData, RadioThermUpdate, async_get_data

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=15)


class RadioThermUpdateCoordinator(DataUpdateCoordinator[RadioThermUpdate]):
    """DataUpdateCoordinator to gather data for radio thermostats."""

    def __init__(
        self, hass: HomeAssistant, init_data: RadioThermInitData, hold_temp: bool
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        self.init_data = init_data
        self.hold_temp = hold_temp
        self._description = f"{init_data.name} ({init_data.host})"
        super().__init__(
            hass,
            _LOGGER,
            name=f"radiotherm {self.init_data.name}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> RadioThermUpdate:
        """Update data from the thermostat."""
        try:
            return await async_get_data(self.hass, self.init_data.tstat)
        except RadiothermTstatError as ex:
            raise UpdateFailed(
                f"{self._description} was busy (invalid value returned): {ex}"
            ) from ex
        except timeout as ex:
            raise UpdateFailed(
                f"{self._description}) timed out waiting for a response: {ex}"
            ) from ex
