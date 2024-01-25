"""Teslemetry Data Coordinator."""
from datetime import timedelta
from typing import Any

from tesla_fleet_api.exceptions import TeslaFleetError, VehicleOffline
from tesla_fleet_api.vehiclespecific import VehicleSpecific

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, TeslemetryState

SYNC_INTERVAL = 60


class TeslemetryVehicleDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Teslemetry API."""

    def __init__(self, hass: HomeAssistant, api: VehicleSpecific) -> None:
        """Initialize Teslemetry Data Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Teslemetry Vehicle",
            update_interval=timedelta(seconds=SYNC_INTERVAL),
        )
        self.api = api

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh."""
        try:
            response = await self.api.wake_up()
            if response["response"]["state"] != TeslemetryState.ONLINE:
                # The first refresh will fail, so retry later
                raise ConfigEntryNotReady("Vehicle is not online")
        except TeslaFleetError as e:
            # The first refresh will also fail, so retry later
            raise ConfigEntryNotReady from e
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Teslemetry API."""

        try:
            data = await self.api.vehicle_data()
        except VehicleOffline:
            self.data["state"] = TeslemetryState.OFFLINE
            return self.data
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

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
