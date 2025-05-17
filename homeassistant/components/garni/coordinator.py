"""The GARNI Data Update Coordinator."""

from __future__ import annotations

import logging

from aioccl import CCLDevice, CCLSensor

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GarniCoordinator(DataUpdateCoordinator):
    """Class to manage processing GARNI data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: CCLDevice,
    ) -> None:
        """Initialize global GARNI data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            always_update=True,
        )
        self.device: CCLDevice = device
        self._data: dict[str, dict[str, CCLSensor]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, CCLSensor]]:
        """Fetch data from GARNI device."""
        try:
            return self.device.get_data
        except Exception as err:
            raise UpdateFailed(f"Error updating from API: {err}") from err

    def async_push_update(self, data) -> None:
        """Process data and update coordinator."""
        self._data = data
        self.async_set_updated_data(self._data)
