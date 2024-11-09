"""Tesla Fleet Data Coordinator."""

from datetime import datetime, timedelta
from typing import Any

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.const import VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    InvalidToken,
    LoginRequired,
    OAuthExpired,
    RateLimited,
    TeslaFleetError,
    VehicleOffline,
)
from tesla_fleet_api.ratecalculator import RateCalculator

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, TeslaFleetState

VEHICLE_INTERVAL_SECONDS = 90
VEHICLE_INTERVAL = timedelta(seconds=VEHICLE_INTERVAL_SECONDS)
VEHICLE_WAIT = timedelta(minutes=15)

ENERGY_INTERVAL_SECONDS = 60
ENERGY_INTERVAL = timedelta(seconds=ENERGY_INTERVAL_SECONDS)

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


class TeslaFleetVehicleDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the TeslaFleet API."""

    updated_once: bool
    pre2021: bool
    last_active: datetime
    rate: RateCalculator

    def __init__(
        self, hass: HomeAssistant, api: VehicleSpecific, product: dict
    ) -> None:
        """Initialize TeslaFleet Vehicle Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Tesla Fleet Vehicle",
            update_interval=VEHICLE_INTERVAL,
        )
        self.api = api
        self.data = flatten(product)
        self.updated_once = False
        self.last_active = datetime.now()
        self.rate = RateCalculator(200, 86400, VEHICLE_INTERVAL_SECONDS, 3600, 5)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using TeslaFleet API."""

        try:
            # Check if the vehicle is awake using a non-rate limited API call
            if self.data["state"] != TeslaFleetState.ONLINE:
                response = await self.api.vehicle()
                self.data["state"] = response["response"]["state"]

            if self.data["state"] != TeslaFleetState.ONLINE:
                return self.data

            # This is a rated limited API call
            self.rate.consume()
            response = await self.api.vehicle_data(endpoints=ENDPOINTS)
            data = response["response"]

        except VehicleOffline:
            self.data["state"] = TeslaFleetState.ASLEEP
            return self.data
        except RateLimited as e:
            LOGGER.warning(
                "%s rate limited, will retry in %s seconds",
                self.name,
                e.data.get("after"),
            )
            if "after" in e.data:
                self.update_interval = timedelta(seconds=int(e.data["after"]))
            return self.data
        except (InvalidToken, OAuthExpired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        # Calculate ideal refresh interval
        self.update_interval = timedelta(seconds=self.rate.calculate())

        self.updated_once = True

        if self.api.pre2021 and data["state"] == TeslaFleetState.ONLINE:
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


class TeslaFleetEnergySiteLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site live status from the TeslaFleet API."""

    updated_once: bool

    def __init__(self, hass: HomeAssistant, api: EnergySpecific) -> None:
        """Initialize TeslaFleet Energy Site Live coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Tesla Fleet Energy Site Live",
            update_interval=timedelta(seconds=10),
        )
        self.api = api
        self.data = {}
        self.updated_once = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using TeslaFleet API."""

        self.update_interval = ENERGY_INTERVAL

        try:
            data = (await self.api.live_status())["response"]
        except RateLimited as e:
            LOGGER.warning(
                "%s rate limited, will retry in %s seconds",
                self.name,
                e.data.get("after"),
            )
            if "after" in e.data:
                self.update_interval = timedelta(seconds=int(e.data["after"]))
            return self.data
        except (InvalidToken, OAuthExpired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        # Convert Wall Connectors from array to dict
        data["wall_connectors"] = {
            wc["din"]: wc for wc in (data.get("wall_connectors") or [])
        }

        self.updated_once = True
        return data


class TeslaFleetEnergySiteInfoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site info from the TeslaFleet API."""

    updated_once: bool

    def __init__(self, hass: HomeAssistant, api: EnergySpecific, product: dict) -> None:
        """Initialize TeslaFleet Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Tesla Fleet Energy Site Info",
            update_interval=timedelta(seconds=15),
        )
        self.api = api
        self.data = flatten(product)
        self.updated_once = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using TeslaFleet API."""

        self.update_interval = ENERGY_INTERVAL

        try:
            data = (await self.api.site_info())["response"]
        except RateLimited as e:
            LOGGER.warning(
                "%s rate limited, will retry in %s seconds",
                self.name,
                e.data.get("after"),
            )
            if "after" in e.data:
                self.update_interval = timedelta(seconds=int(e.data["after"]))
            return self.data
        except (InvalidToken, OAuthExpired, LoginRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        self.updated_once = True
        return flatten(data)
