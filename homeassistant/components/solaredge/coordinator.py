"""Provides the data update coordinators for SolarEdge."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any

from solaredge import Solaredge
from stringcase import snakecase

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DETAILS_UPDATE_DELAY,
    ENERGY_DETAILS_DELAY,
    INVENTORY_UPDATE_DELAY,
    LOGGER,
    OVERVIEW_UPDATE_DELAY,
    POWER_FLOW_UPDATE_DELAY,
)


class SolarEdgeDataService(ABC):
    """Get and update the latest data."""

    coordinator: DataUpdateCoordinator[None]

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the data object."""
        self.api = api
        self.site_id = site_id

        self.data: dict[str, Any] = {}
        self.attributes: dict[str, Any] = {}

        self.hass = hass

    @callback
    def async_setup(self) -> None:
        """Coordinator creation."""
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            LOGGER,
            name=str(self),
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    @abstractmethod
    def update_interval(self) -> timedelta:
        """Update interval."""

    @abstractmethod
    def update(self) -> None:
        """Update data in executor."""

    async def async_update_data(self) -> None:
        """Update data."""
        await self.hass.async_add_executor_job(self.update)


class SolarEdgeOverviewDataService(SolarEdgeDataService):
    """Get and update the latest overview data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return OVERVIEW_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_overview(self.site_id)
            overview = data["overview"]
        except KeyError as ex:
            raise UpdateFailed("Missing overview data, skipping update") from ex

        self.data = {}

        energy_keys = ["lifeTimeData", "lastYearData", "lastMonthData", "lastDayData"]
        for key, value in overview.items():
            if key in energy_keys:
                data = value["energy"]
            elif key in ["currentPower"]:
                data = value["power"]
            else:
                data = value
            self.data[key] = data

        # Sanity check the energy values. SolarEdge API sometimes report "lifetimedata" of zero,
        # while values for last Year, Month and Day energy are still OK.
        # See https://github.com/home-assistant/core/issues/59285 .
        if set(energy_keys).issubset(self.data.keys()):
            for index, key in enumerate(energy_keys, start=1):
                # All coming values in list should be larger than the current value.
                if any(self.data[k] > self.data[key] for k in energy_keys[index:]):
                    LOGGER.info(
                        "Ignoring invalid energy value %s for %s", self.data[key], key
                    )
                    self.data.pop(key)

        LOGGER.debug("Updated SolarEdge overview: %s", self.data)


class SolarEdgeDetailsDataService(SolarEdgeDataService):
    """Get and update the latest details data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return DETAILS_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""

        try:
            data = self.api.get_details(self.site_id)
            details = data["details"]
        except KeyError as ex:
            raise UpdateFailed("Missing details data, skipping update") from ex

        self.data = {}
        self.attributes = {}

        for key, value in details.items():
            key = snakecase(key)

            if key in ["primary_module"]:
                for module_key, module_value in value.items():
                    self.attributes[snakecase(module_key)] = module_value
            elif key in [
                "peak_power",
                "type",
                "name",
                "last_update_time",
                "installation_date",
            ]:
                self.attributes[key] = value
            elif key == "status":
                self.data["status"] = value

        LOGGER.debug(
            "Updated SolarEdge details: %s, %s",
            self.data.get("status"),
            self.attributes,
        )


class SolarEdgeInventoryDataService(SolarEdgeDataService):
    """Get and update the latest inventory data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return INVENTORY_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_inventory(self.site_id)
            inventory = data["Inventory"]
        except KeyError as ex:
            raise UpdateFailed("Missing inventory data, skipping update") from ex

        self.data = {}
        self.attributes = {}

        for key, value in inventory.items():
            self.data[key] = len(value)
            self.attributes[key] = {key: value}

        LOGGER.debug("Updated SolarEdge inventory: %s, %s", self.data, self.attributes)


class SolarEdgeEnergyDetailsService(SolarEdgeDataService):
    """Get and update the latest power flow data."""

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the power flow data service."""
        super().__init__(hass, api, site_id)

        self.unit = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return ENERGY_DETAILS_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            now = datetime.now()
            today = date.today()
            midnight = datetime.combine(today, datetime.min.time())
            data = self.api.get_energy_details(
                self.site_id,
                midnight,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                meters=None,
                time_unit="DAY",
            )
            energy_details = data["energyDetails"]
        except KeyError as ex:
            raise UpdateFailed("Missing power flow data, skipping update") from ex

        if "meters" not in energy_details:
            LOGGER.debug(
                "Missing meters in energy details data. Assuming site does not have any"
            )
            return

        self.data = {}
        self.attributes = {}
        self.unit = energy_details["unit"]

        for meter in energy_details["meters"]:
            if "type" not in meter or "values" not in meter:
                continue
            if meter["type"] not in [
                "Production",
                "SelfConsumption",
                "FeedIn",
                "Purchased",
                "Consumption",
            ]:
                continue
            if len(meter["values"][0]) == 2:
                self.data[meter["type"]] = meter["values"][0]["value"]
                self.attributes[meter["type"]] = {"date": meter["values"][0]["date"]}

        LOGGER.debug(
            "Updated SolarEdge energy details: %s, %s", self.data, self.attributes
        )


class SolarEdgePowerFlowDataService(SolarEdgeDataService):
    """Get and update the latest power flow data."""

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the power flow data service."""
        super().__init__(hass, api, site_id)

        self.unit = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return POWER_FLOW_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_current_power_flow(self.site_id)
            power_flow = data["siteCurrentPowerFlow"]
        except KeyError as ex:
            raise UpdateFailed("Missing power flow data, skipping update") from ex

        power_from = []
        power_to = []

        if "connections" not in power_flow:
            LOGGER.debug(
                "Missing connections in power flow data. Assuming site does not"
                " have any"
            )
            return

        for connection in power_flow["connections"]:
            power_from.append(connection["from"].lower())
            power_to.append(connection["to"].lower())

        self.data = {}
        self.attributes = {}
        self.unit = power_flow["unit"]

        for key, value in power_flow.items():
            if key in ["LOAD", "PV", "GRID", "STORAGE"]:
                self.data[key] = value.get("currentPower")
                self.attributes[key] = {"status": value["status"]}

            if key in ["GRID"]:
                export = key.lower() in power_to
                if self.data[key]:
                    self.data[key] *= -1 if export else 1
                self.attributes[key]["flow"] = "export" if export else "import"

            if key in ["STORAGE"]:
                charge = key.lower() in power_to
                if self.data[key]:
                    self.data[key] *= -1 if charge else 1
                self.attributes[key]["flow"] = "charge" if charge else "discharge"
                self.attributes[key]["soc"] = value["chargeLevel"]

        LOGGER.debug("Updated SolarEdge power flow: %s, %s", self.data, self.attributes)
