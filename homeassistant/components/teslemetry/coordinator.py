"""Teslemetry Data Coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from tesla_fleet_api.const import TeslaEnergyPeriod, VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.teslemetry import EnergySite, Vehicle

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import TeslemetryConfigEntry

from .const import ENERGY_HISTORY_FIELDS, LOGGER
from .helpers import flatten

VEHICLE_INTERVAL = timedelta(seconds=60)
VEHICLE_WAIT = timedelta(minutes=15)
ENERGY_LIVE_INTERVAL = timedelta(seconds=30)
ENERGY_INFO_INTERVAL = timedelta(seconds=30)
ENERGY_HISTORY_INTERVAL = timedelta(seconds=60)

ENDPOINTS = [
    VehicleDataEndpoint.CHARGE_STATE,
    VehicleDataEndpoint.CLIMATE_STATE,
    VehicleDataEndpoint.DRIVE_STATE,
    VehicleDataEndpoint.LOCATION_DATA,
    VehicleDataEndpoint.VEHICLE_STATE,
    VehicleDataEndpoint.VEHICLE_CONFIG,
]


class TeslemetryVehicleDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Teslemetry API."""

    config_entry: TeslemetryConfigEntry
    last_active: datetime

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: Vehicle,
        product: dict,
    ) -> None:
        """Initialize Teslemetry Vehicle Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Vehicle",
            update_interval=VEHICLE_INTERVAL,
        )
        self.api = api
        self.data = flatten(product)
        self.last_active = datetime.now()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using Teslemetry API."""

        try:
            data = (await self.api.vehicle_data(endpoints=ENDPOINTS))["response"]
        except (InvalidToken, SubscriptionRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        return flatten(data)


class TeslemetryEnergySiteLiveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site live status from the Teslemetry API."""

    config_entry: TeslemetryConfigEntry
    updated_once: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: EnergySite,
        data: dict,
    ) -> None:
        """Initialize Teslemetry Energy Site Live coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Energy Site Live",
            update_interval=ENERGY_LIVE_INTERVAL,
        )
        self.api = api

        # Convert Wall Connectors from array to dict
        data["wall_connectors"] = {
            wc["din"]: wc for wc in (data.get("wall_connectors") or [])
        }
        self.data = data

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""

        try:
            data = (await self.api.live_status())["response"]
        except (InvalidToken, SubscriptionRequired) as e:
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

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: EnergySite,
        product: dict,
    ) -> None:
        """Initialize Teslemetry Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Teslemetry Energy Site Info",
            update_interval=ENERGY_INFO_INTERVAL,
        )
        self.api = api
        self.data = product

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""

        try:
            data = (await self.api.site_info())["response"]
        except (InvalidToken, SubscriptionRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        return flatten(data)


class TeslemetryEnergyHistoryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site info from the Teslemetry API."""

    config_entry: TeslemetryConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslemetryConfigEntry,
        api: EnergySite,
    ) -> None:
        """Initialize Teslemetry Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Teslemetry Energy History {api.energy_site_id}",
            update_interval=ENERGY_HISTORY_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site data using Teslemetry API."""

        try:
            data = (await self.api.energy_history(TeslaEnergyPeriod.DAY))["response"]
        except (InvalidToken, SubscriptionRequired) as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        # Add all time periods together
        output = dict.fromkeys(ENERGY_HISTORY_FIELDS, 0)
        for period in data.get("time_series", []):
            for key in ENERGY_HISTORY_FIELDS:
                output[key] += period.get(key, 0)

        return output
