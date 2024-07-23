"""Teslemetry Data Coordinator."""

from datetime import datetime, timedelta
from typing import Any

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.const import VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    Forbidden,
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
    VehicleOffline,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, TeslemetryState

VEHICLE_INTERVAL = timedelta(seconds=30)
VEHICLE_WAIT = timedelta(minutes=15)
ENERGY_LIVE_INTERVAL = timedelta(seconds=30)
ENERGY_INFO_INTERVAL = timedelta(seconds=30)

ENDPOINTS = [
    VehicleDataEndpoint.CHARGE_STATE,
    VehicleDataEndpoint.CLIMATE_STATE,
    VehicleDataEndpoint.DRIVE_STATE,
    VehicleDataEndpoint.LOCATION_DATA,
    VehicleDataEndpoint.VEHICLE_STATE,
    VehicleDataEndpoint.VEHICLE_CONFIG,
]


def flatten(data: dict[str, Any], parent: str | None = None) -> dict[str, Any]:
    """Flatten the data structure."""
    result = {}
    for key, value in data.items():
        if parent:
            key = f"{parent}_{key}"
        if isinstance(value, dict):
            result.update(flatten(value, key))
        else:
            result[key] = value
    return result


class TeslemetryVehicleDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Teslemetry API."""

    updated_once: bool
    pre2021: bool
    last_active: datetime

    def __init__(
        self, hass: HomeAssistant, api: VehicleSpecific, product: dict
    ) -> None:
        """Initialize Teslemetry Vehicle Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Teslemetry Vehicle",
            update_interval=VEHICLE_INTERVAL,
        )
        self.api = api
        self.data = flatten(product)
        self.updated_once = False
        self.last_active = datetime.now()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Teslemetry API."""

        self.update_interval = VEHICLE_INTERVAL

        try:
            if self.data["state"] != TeslemetryState.ONLINE:
                response = await self.api.vehicle()
                self.data["state"] = response["response"]["state"]

            if self.data["state"] != TeslemetryState.ONLINE:
                return self.data

            response = await self.api.vehicle_data(endpoints=ENDPOINTS)
            data = response["response"]

        except VehicleOffline:
            self.data["state"] = TeslemetryState.OFFLINE
            return self.data
        except InvalidToken as e:
            raise ConfigEntryAuthFailed from e
        except SubscriptionRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        self.updated_once = True

        if self.api.pre2021 and data["state"] == TeslemetryState.ONLINE:
            # Handle pre-2021 vehicles which cannot sleep by themselves
            if (
                data["charge_state"].get("charging_state") == "Charging"
                or data["vehicle_state"].get("is_user_present")
                or data["vehicle_state"].get("sentry_mode")
            ):
                # Vehicle is active, reset timer
                self.last_active = datetime.now()
            else:
                elapsed = datetime.now() - self.last_active
                if elapsed > timedelta(minutes=20):
                    # Vehicle didn't sleep, try again in 15 minutes
                    self.last_active = datetime.now()
                elif elapsed > timedelta(minutes=15):
                    # Let vehicle go to sleep now
                    self.update_interval = VEHICLE_WAIT

        return flatten(data)


class TeslemetryEnergySiteLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site live status from the Teslemetry API."""

    updated_once: bool

    def __init__(self, hass: HomeAssistant, api: EnergySpecific) -> None:
        """Initialize Teslemetry Energy Site Live coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Teslemetry Energy Site Live",
            update_interval=ENERGY_LIVE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""

        try:
            data = (await self.api.live_status())["response"]
        except (InvalidToken, Forbidden, SubscriptionRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        # Convert Wall Connectors from array to dict
        data["wall_connectors"] = {
            wc["din"]: wc for wc in (data.get("wall_connectors") or [])
        }

        return data


class TeslemetryEnergySiteInfoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site info from the Teslemetry API."""

    updated_once: bool

    def __init__(self, hass: HomeAssistant, api: EnergySpecific, product: dict) -> None:
        """Initialize Teslemetry Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Teslemetry Energy Site Info",
            update_interval=ENERGY_INFO_INTERVAL,
        )
        self.api = api
        self.data = product

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""

        try:
            data = (await self.api.site_info())["response"]
        except (InvalidToken, Forbidden, SubscriptionRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        return flatten(data)
