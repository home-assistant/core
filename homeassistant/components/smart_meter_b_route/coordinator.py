"""DataUpdateCoordinator for the Smart Meter B-route integration."""

import logging
from typing import Any

from momonga import Momonga, MomongaError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
    ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
    ATTR_API_INSTANTANEOUS_POWER,
    ATTR_API_TOTAL_CONSUMPTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BRouteUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The B Route update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: str,
        id: str,
        password: str,
    ) -> None:
        """Initialize."""

        self.api = Momonga(dev=device, rbid=id, pwd=password)
        self.device = device
        self.bid = id

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_setup(self) -> None:
        await self.hass.async_add_executor_job(
            self.api.open,
        )

    def _get_data(self) -> dict[str, int | float]:
        """Get the data from API."""
        current = self.api.get_instantaneous_current()
        return {
            ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE: current["r phase current"],
            ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE: current["t phase current"],
            ATTR_API_INSTANTANEOUS_POWER: self.api.get_instantaneous_power(),
            ATTR_API_TOTAL_CONSUMPTION: self.api.get_measured_cumulative_energy(),
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data."""
        try:
            return await self.hass.async_add_executor_job(self._get_data)
        except MomongaError as error:
            raise UpdateFailed(error) from error
