"""Teslemetry Data Coordinator."""
from datetime import timedelta
import logging
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError
from tesla_fleet_api.vehiclespecific import VehicleSpecific

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SYNC_INTERVAL = 300

_LOGGER = logging.getLogger(__name__)


class TeslemetryVehicleDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Teslemetry API."""

    def __init__(self, hass: HomeAssistant, api: VehicleSpecific) -> None:
        """Initialize Teslemetry Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Teslemetry Vehicle",
            update_interval=timedelta(seconds=SYNC_INTERVAL),
        )
        self._api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Teslemetry API."""
        try:
            data = await self._api.vehicle_data()
        except TeslaFleetError as e:
            raise UpdateFailed from e

        return self._flatten(data["response"])

    def _flatten(
        self, data: dict[str, Any], parent: str | None = None
    ) -> dict[str, Any]:
        """Flatten the data structure."""
        result = {}
        for key, value in data.items():
            if parent:
                key = f"{parent}_{key}"
            if isinstance(value, dict):
                result.update(self._flatten(value, key))
            else:
                result[key] = value
        return result
