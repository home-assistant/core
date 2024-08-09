"""DataUpdateCoordinator for the Smart Meter B-route integration."""

from datetime import timedelta
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BRouteUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The B Route update coordinator."""

    api: Momonga

    def __init__(
        self,
        hass: HomeAssistant,
        device: str,
        id: str,
        password: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""

        self.api = Momonga(dev=device, rbid=id, pwd=password)
        self.bid = id

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data."""
        data = {}
        try:
            current = await self.hass.async_add_executor_job(
                self.api.get_instantaneous_current
            )
            data[ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE] = current["r phase current"]
            data[ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE] = current["t phase current"]
            data[ATTR_API_INSTANTANEOUS_POWER] = await self.hass.async_add_executor_job(
                self.api.get_instantaneous_power
            )
            data[ATTR_API_TOTAL_CONSUMPTION] = await self.hass.async_add_executor_job(
                self.api.get_measured_cumulative_energy
            )
        except MomongaError as error:
            raise UpdateFailed(error) from error

        return data
