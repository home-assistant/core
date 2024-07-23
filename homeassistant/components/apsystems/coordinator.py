"""The coordinator for APsystems local API integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from APsystemsEZ1 import APsystemsEZ1M, ReturnOutputData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class InverterNotAvailable(Exception):
    """Error used when Device is offline."""


class ApSystemsDataCoordinator(DataUpdateCoordinator):
    """Coordinator used for all sensors."""

    def __init__(self, hass: HomeAssistant, api: APsystemsEZ1M) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="APSystems Data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=12),
        )
        self.api = api
        self.always_update = True

    async def _async_update_data(self) -> ReturnOutputData:
        return await self.api.get_output_data()
