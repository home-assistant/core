"""Teslemetry Data Coordinator."""

from datetime import timedelta
from typing import Any

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.const import VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
    VehicleOffline,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, TeslemetryState

SYNC_INTERVAL = 60
ENDPOINTS = [
    VehicleDataEndpoint.CHARGE_STATE,
    VehicleDataEndpoint.CLIMATE_STATE,
    VehicleDataEndpoint.DRIVE_STATE,
    VehicleDataEndpoint.LOCATION_DATA,
    VehicleDataEndpoint.VEHICLE_STATE,
    VehicleDataEndpoint.VEHICLE_CONFIG,
]


class TeslemetryDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Base class for Teslemetry Data Coordinators."""

    name: str

    def __init__(
        self, hass: HomeAssistant, api: VehicleSpecific | EnergySpecific
    ) -> None:
        """Initialize Teslemetry Vehicle Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=self.name,
            update_interval=timedelta(seconds=SYNC_INTERVAL),
        )
        self.api = api


class TeslemetryVehicleDataCoordinator(TeslemetryDataCoordinator):
    """Class to manage fetching data from the Teslemetry API."""

    name = "Teslemetry Vehicle"

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh."""
        try:
            response = await self.api.wake_up()
            if response["response"]["state"] != TeslemetryState.ONLINE:
                # The first refresh will fail, so retry later
                raise ConfigEntryNotReady("Vehicle is not online")
        except InvalidToken as e:
            raise ConfigEntryAuthFailed from e
        except SubscriptionRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            # The first refresh will also fail, so retry later
            raise ConfigEntryNotReady from e
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Teslemetry API."""

        try:
            data = await self.api.vehicle_data(endpoints=ENDPOINTS)
        except VehicleOffline:
            self.data["state"] = TeslemetryState.OFFLINE
            return self.data
        except InvalidToken as e:
            raise ConfigEntryAuthFailed from e
        except SubscriptionRequired as e:
            raise ConfigEntryAuthFailed from e
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


class TeslemetryEnergyDataCoordinator(TeslemetryDataCoordinator):
    """Class to manage fetching data from the Teslemetry API."""

    name = "Teslemetry Energy Site"

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""

        try:
            data = await self.api.live_status()
        except InvalidToken as e:
            raise ConfigEntryAuthFailed from e
        except SubscriptionRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        # Convert Wall Connectors from array to dict
        data["response"]["wall_connectors"] = {
            wc["din"]: wc for wc in (data["response"].get("wall_connectors") or [])
        }

        return data["response"]
