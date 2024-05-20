"""The coordinator for APsystems local API integration."""

from __future__ import annotations

from datetime import timedelta

from APsystemsEZ1 import APsystemsEZ1M, ReturnOutputData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER


class ApSystemsDataCoordinator(DataUpdateCoordinator[ReturnOutputData]):
    """Coordinator used for all sensors."""

    def __init__(self, hass: HomeAssistant, api: APsystemsEZ1M) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="APSystems Data",
            update_interval=timedelta(seconds=12),
        )
        self.api = api

    async def _async_update_data(self) -> ReturnOutputData:
        return await self.api.get_output_data()
