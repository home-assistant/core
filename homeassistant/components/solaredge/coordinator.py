"""Provides the data update coordinators for SolarEdge."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from aiosolaredge import SolarEdge
from solaredge_web import EnergyData, SolarEdgeWeb, TimeUnit
from stringcase import snakecase

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import (
    CONF_SITE_ID,
    DETAILS_UPDATE_DELAY,
    DOMAIN,
    ENERGY_DETAILS_DELAY,
    INVENTORY_UPDATE_DELAY,
    LOGGER,
    MODULE_STATISTICS_UPDATE_DELAY,
    OVERVIEW_UPDATE_DELAY,
    POWER_FLOW_UPDATE_DELAY,
)

if TYPE_CHECKING:
    from .types import SolarEdgeConfigEntry


class SolarEdgeDataService(ABC):
    """Get and update the latest data."""

    coordinator: DataUpdateCoordinator[None]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarEdgeConfigEntry,
        api: SolarEdge,
        site_id: str,
    ) -> None:
        """Initialize the data object."""
        self.api = api
        self.site_id = site_id

        self.data: dict[str, Any] = {}
        self.attributes: dict[str, Any] = {}

        self.hass = hass
        self.config_entry = config_entry

    @callback
    def async_setup(self) -> None:
        """Coordinator creation."""
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            LOGGER,
            config_entry=self.config_entry,
            name=str(self),
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    @abstractmethod
    def update_interval(self) -> timedelta:
        """Update interval."""

    @abstractmethod
    async def async_update_data(self) -> None:
        """Update data."""


class SolarEdgeOverviewDataService(SolarEdgeDataService):
    """Get and update the latest overview data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return OVERVIEW_UPDATE_DELAY

    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = await self.api.get_overview(self.site_id)
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
                    LOGGER.warning(
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

    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""

        try:
            data = await self.api.get_details(self.site_id)
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

    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = await self.api.get_inventory(self.site_id)
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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarEdgeConfigEntry,
        api: SolarEdge,
        site_id: str,
    ) -> None:
        """Initialize the power flow data service."""
        super().__init__(hass, config_entry, api, site_id)

        self.unit = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return ENERGY_DETAILS_DELAY

    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            now = datetime.now()
            today = date.today()
            midnight = datetime.combine(today, datetime.min.time())
            data = await self.api.get_energy_details(
                self.site_id,
                midnight,
                now,
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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarEdgeConfigEntry,
        api: SolarEdge,
        site_id: str,
    ) -> None:
        """Initialize the power flow data service."""
        super().__init__(hass, config_entry, api, site_id)

        self.unit = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return POWER_FLOW_UPDATE_DELAY

    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = await self.api.get_current_power_flow(self.site_id)
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


class SolarEdgeModulesCoordinator(DataUpdateCoordinator[None]):
    """Handle fetching SolarEdge Modules data and inserting statistics."""

    config_entry: SolarEdgeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarEdgeConfigEntry,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="SolarEdge Modules",
            # API refreshes every 15 minutes, but since we only have statistics
            # and no sensors, refresh every 12h.
            update_interval=MODULE_STATISTICS_UPDATE_DELAY,
        )
        self.api = SolarEdgeWeb(
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            site_id=config_entry.data[CONF_SITE_ID],
            session=aiohttp_client.async_get_clientsession(hass),
        )
        self.site_id = config_entry.data[CONF_SITE_ID]
        self.title = config_entry.title

        @callback
        def _dummy_listener() -> None:
            pass

        # Force the coordinator to periodically update by registering a listener.
        # Needed because there are no sensors added.
        self.async_add_listener(_dummy_listener)

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint and update statistics."""
        equipment: dict[int, dict[str, Any]] = await self.api.async_get_equipment()
        # We fetch last week's data from the API and refresh every 12h so we overwrite recent
        # statistics. This is intended to allow adding any corrected/updated data from the API.
        energy_data_list: list[EnergyData] = await self.api.async_get_energy_data(
            TimeUnit.WEEK
        )
        if not energy_data_list:
            LOGGER.warning(
                "No data received from SolarEdge API for site: %s", self.site_id
            )
            return
        last_sums = await self._async_get_last_sums(
            equipment.keys(),
            energy_data_list[0].start_time.replace(
                tzinfo=dt_util.get_default_time_zone()
            ),
        )
        for equipment_id, equipment_data in equipment.items():
            display_name = equipment_data.get(
                "displayName", f"Equipment {equipment_id}"
            )
            statistic_id = self.get_statistic_id(equipment_id)
            statistic_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.ARITHMETIC,
                has_sum=True,
                name=f"{self.title} {display_name}",
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_class=EnergyConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            )
            statistic_sum = last_sums[statistic_id]
            statistics = []
            current_hour_sum = 0.0
            current_hour_count = 0
            for energy_data in energy_data_list:
                start_time = energy_data.start_time.replace(
                    tzinfo=dt_util.get_default_time_zone()
                )
                value = energy_data.values.get(equipment_id, 0.0)
                current_hour_sum += value
                current_hour_count += 1
                if start_time.minute != 45:
                    continue
                # API returns data every 15 minutes; aggregate to 1-hour statistics
                # when we reach the energy_data for the last 15 minutes of the hour.
                current_avg = current_hour_sum / current_hour_count
                statistic_sum += current_avg
                statistics.append(
                    StatisticData(
                        start=start_time - timedelta(minutes=45),
                        state=current_avg,
                        sum=statistic_sum,
                    )
                )
                current_hour_sum = 0.0
                current_hour_count = 0
            LOGGER.debug(
                "Adding %s statistics for %s %s",
                len(statistics),
                statistic_id,
                display_name,
            )
            async_add_external_statistics(self.hass, statistic_metadata, statistics)

    def get_statistic_id(self, equipment_id: int) -> str:
        """Return the statistic ID for this equipment_id."""
        return f"{DOMAIN}:{self.site_id}_{equipment_id}"

    async def _async_get_last_sums(
        self, equipment_ids: Iterable[int], start_time: datetime
    ) -> dict[str, float]:
        """Get the last sum from the recorder before start_time for each statistic."""
        start = start_time - timedelta(hours=1)
        statistic_ids = {self.get_statistic_id(eq_id) for eq_id in equipment_ids}
        LOGGER.debug(
            "Getting sum for %s statistic IDs at: %s", len(statistic_ids), start
        )
        current_stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start,
            start + timedelta(seconds=1),
            statistic_ids,
            "hour",
            None,
            {"sum"},
        )
        result = {}
        for statistic_id in statistic_ids:
            if statistic_id in current_stats:
                statistic_sum = current_stats[statistic_id][0]["sum"]
            else:
                # If no statistics found right before start_time, try to get the last statistic
                # but use it only if it's before start_time.
                # This is needed if the integration hasn't run successfully for at least a week.
                last_stat = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
                )
                if (
                    last_stat
                    and last_stat[statistic_id][0]["start"] < start_time.timestamp()
                ):
                    statistic_sum = last_stat[statistic_id][0]["sum"]
                else:
                    # Expected for new installations or if the statistics were cleared,
                    # e.g. from the developer tools
                    statistic_sum = 0.0
            assert isinstance(statistic_sum, float)
            result[statistic_id] = statistic_sum
        return result
