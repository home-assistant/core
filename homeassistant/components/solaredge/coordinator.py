"""Provides the data update coordinators for SolarEdge."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, override

from aiosolaredge import SolarEdge
from aiosolaredge.monitoring import BasicMonitoring, period_start
from aiosolaredge.v2 import (
    AuthenticationError,
    InvalidResponseError,
    PermissionDeniedError,
    RateLimitError,
    Reading,
    SolarEdgeV2Error,
)
from solaredge_web import EnergyData, SolarEdgeWeb

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_list_statistic_ids,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify, snakecase
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
    STORAGE_DATA_UPDATE_DELAY,
)
from .v2_budget import get_budget, retry_deadline
from .v2_runtime import HOUR, MAX_CALLS, PERIODS, WINDOW, safe_metadata

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
    @override
    def update_interval(self) -> timedelta:
        """Update interval."""
        return OVERVIEW_UPDATE_DELAY

    @override
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
            elif key == "currentPower":
                data = value["power"]
            else:
                data = value
            self.data[key] = data

        # Sanity check the energy values. SolarEdge API sometimes
        # reports "lifetimedata" of zero,
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
    @override
    def update_interval(self) -> timedelta:
        """Update interval."""
        return DETAILS_UPDATE_DELAY

    @override
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

            if key == "primary_module":
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
    @override
    def update_interval(self) -> timedelta:
        """Update interval."""
        return INVENTORY_UPDATE_DELAY

    @override
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
    @override
    def update_interval(self) -> timedelta:
        """Update interval."""
        return ENERGY_DETAILS_DELAY

    @override
    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            now = dt_util.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
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
    @override
    def update_interval(self) -> timedelta:
        """Update interval."""
        return POWER_FLOW_UPDATE_DELAY

    @override
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

            if key == "GRID":
                export = key.lower() in power_to
                if self.data[key]:
                    self.data[key] *= -1 if export else 1
                self.data["grid_flow_direction"] = "export" if export else "import"

            if key == "STORAGE":
                charge = key.lower() in power_to
                if self.data[key]:
                    self.data[key] *= -1 if charge else 1
                self.data["storage_flow_direction"] = (
                    "charge" if charge else "discharge"
                )
                self.data["storage_level"] = value["chargeLevel"]

        LOGGER.debug("Updated SolarEdge power flow: %s, %s", self.data, self.attributes)


class SolarEdgeStorageDataService(SolarEdgeDataService):
    """Get and update the latest storage data."""

    @property
    @override
    def update_interval(self) -> timedelta:
        """Update interval."""
        return STORAGE_DATA_UPDATE_DELAY

    @override
    async def async_update_data(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        now = dt_util.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        data = await self.api.get_storage_data(
            self.site_id,
            start_of_day,
            now,
        )
        storage_data = data.get("storageData")
        if storage_data is None:
            raise UpdateFailed("Storage data not available from API")

        batteries = storage_data.get("batteries")
        if batteries is None:
            raise UpdateFailed("Battery data not available from API")

        self.data = {}
        self.attributes = {}

        if not batteries:
            LOGGER.debug("No batteries found in storage data")
            return

        # Aggregate totals across all batteries
        total_charge_energy = 0.0
        total_discharge_energy = 0.0

        for battery in batteries:
            serial = battery.get("serialNumber")
            if not serial:
                LOGGER.debug("Skipping battery without serialNumber")
                continue

            telemetries = battery.get("telemetries", [])

            if not telemetries:
                continue

            latest = telemetries[-1]

            # Per-battery current values
            self.data[f"{serial}_state_of_charge"] = latest.get(
                "batteryPercentageState"
            )
            self.data[f"{serial}_power"] = latest.get("power")

            # Compute daily charge/discharge delta from lifetime counters
            if len(telemetries) >= 2:
                first = telemetries[0]
                charge_energy = latest.get("lifeTimeEnergyCharged", 0.0) - first.get(
                    "lifeTimeEnergyCharged", 0.0
                )
                discharge_energy = latest.get(
                    "lifeTimeEnergyDischarged", 0.0
                ) - first.get("lifeTimeEnergyDischarged", 0.0)
            else:
                charge_energy = 0.0
                discharge_energy = 0.0

            total_charge_energy += charge_energy
            total_discharge_energy += discharge_energy

            self.data[f"{serial}_charge_energy"] = charge_energy
            self.data[f"{serial}_discharge_energy"] = discharge_energy

        self.data["charge_energy"] = total_charge_energy
        self.data["discharge_energy"] = total_discharge_energy

        LOGGER.debug("Updated SolarEdge storage data: %s", self.data)


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
        self._serial_to_legacy_id: dict[str, str] = {}
        self._legacy_id_map_initialized = False

        @callback
        def _dummy_listener() -> None:
            pass

        # Force the coordinator to periodically update by registering a listener.
        # Needed because there are no sensors added.
        self.async_add_listener(_dummy_listener)

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint and update statistics."""
        equipment: dict[str, dict[str, Any]] = {
            equipment_id: equipment_data
            for equipment_id, equipment_data in (
                await self.api.async_get_equipment()
            ).items()
            if equipment_data.get("type") in ("INVERTER", "STRING", "OPTIMIZER")
        }
        await self._async_build_legacy_id_map(equipment)
        # We fetch last week's data from the API and refresh
        # every 12h so we overwrite recent statistics. This is
        # intended to allow adding any corrected/updated data.
        energy_data_list: list[EnergyData] = await self.api.async_get_energy_data()
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
            display_name = equipment_data.get("name", f"Equipment {equipment_id}")
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
            for energy_data in energy_data_list:
                start_time = energy_data.start_time.replace(
                    tzinfo=dt_util.get_default_time_zone()
                )
                value = energy_data.values.get(equipment_id, 0.0)
                statistic_sum += value
                statistics.append(
                    StatisticData(
                        start=start_time,
                        state=value,
                        sum=statistic_sum,
                    )
                )
            LOGGER.debug(
                "Adding %s statistics for %s %s",
                len(statistics),
                statistic_id,
                display_name,
            )
            async_add_external_statistics(self.hass, statistic_metadata, statistics)

    async def _async_build_legacy_id_map(
        self, equipment: dict[str, dict[str, Any]]
    ) -> None:
        """Build a map from serial numbers to legacy numeric statistic IDs.

        The old API returned numeric equipment IDs; the new API returns serials.
        To preserve existing statistics, we map each serial's name (the last
        part after splitting by space, e.g. "1.1.1") to the old statistic ID
        by matching the statistic name. This runs once per coordinator lifecycle.
        """
        if self._legacy_id_map_initialized:
            return

        all_stats = await async_list_statistic_ids(self.hass)

        prefix = f"{DOMAIN}:{self.site_id}_"
        # Map the short name (e.g. "1.1.1") to the old numeric statistic ID.
        # Multiple numeric IDs may share the same name, e.g. after a module
        # replacement; those matches are ambiguous and skipped.
        name_to_legacy: dict[str, str] = {}
        ambiguous_names: set[str] = set()
        for stat in all_stats:
            stat_id = stat["statistic_id"]
            if not stat_id.startswith(prefix):
                continue
            suffix = stat_id[len(prefix) :]
            if not suffix.isdigit():
                continue
            name = stat.get("name", "")
            # Use the last part after splitting by space (e.g. "solaredge 1.1.1" -> "1.1.1").
            short_name = name.rsplit(" ", 1)[-1] if name else ""
            if not short_name:
                continue
            if short_name in name_to_legacy:
                del name_to_legacy[short_name]
                ambiguous_names.add(short_name)
            elif short_name not in ambiguous_names:
                name_to_legacy[short_name] = stat_id

        self._legacy_id_map_initialized = True

        if not name_to_legacy and not ambiguous_names:
            return

        # Map each serial to its old statistic ID via the equipment name.
        for serial, data in equipment.items():
            name = data.get("name", "")
            short_name = name.rsplit(" ", 1)[-1] if name else ""
            if not short_name:
                continue
            if short_name in ambiguous_names:
                LOGGER.warning(
                    "Skipping legacy statistics migration for %s %s: multiple "
                    "numeric statistics share the name %s, so the match is "
                    "ambiguous",
                    self.site_id,
                    name,
                    short_name,
                )
                continue
            if short_name in name_to_legacy:
                self._serial_to_legacy_id[serial] = name_to_legacy[short_name]

        if self._serial_to_legacy_id:
            LOGGER.debug(
                "Mapped %s legacy SolarEdge statistics to serials for site %s",
                len(self._serial_to_legacy_id),
                self.site_id,
            )

    def get_statistic_id(self, equipment_id: int | str) -> str:
        """Return the statistic ID for this equipment_id.

        If a legacy numeric ID exists for this serial, reuse it for backward
        compatibility. Otherwise, create a new serial-based ID.
        """
        if isinstance(equipment_id, str) and equipment_id in self._serial_to_legacy_id:
            return self._serial_to_legacy_id[equipment_id]
        if isinstance(equipment_id, str):
            equipment_id = slugify(equipment_id)
        return f"{DOMAIN}:{self.site_id}_{equipment_id}"

    async def _async_get_last_sums(
        self, equipment_ids: Iterable[int | str], start_time: datetime
    ) -> dict[str, float]:
        """Get the last sum from the recorder before start_time for each statistic."""
        statistic_ids = {self.get_statistic_id(eq_id) for eq_id in equipment_ids}
        LOGGER.debug(
            "Getting sum for %s statistic IDs before: %s",
            len(statistic_ids),
            start_time,
        )
        # The statistics are cumulative, so the sums must continue from the last
        # sum before the window. Taking it from the change of the first statistic
        # in the window works even when the previous statistics are older than
        # the window, and unlike the absolute last statistic it is not reset by
        # an earlier update that already wrote statistics inside the window.
        # See https://github.com/home-assistant/core/issues/186653 .
        current_stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start_time,
            None,
            statistic_ids,
            "hour",
            None,
            {"sum", "change"},
        )
        result = {}
        for statistic_id in statistic_ids:
            statistic_sum: float | None = None
            window_stats = current_stats.get(statistic_id) or []
            # The change is relative to the last sum before start_time, so
            # subtracting it from the first statistic that has a sum recovers
            # that sum. Leading statistics without a sum are skipped.
            for stat in window_stats:
                stat_sum = stat["sum"]
                stat_change = stat["change"]
                if stat_sum is not None and stat_change is not None:
                    statistic_sum = stat_sum - stat_change
                    break
            if statistic_sum is None:
                # No statistic in the window has a usable sum, so continue from
                # the last statistic before start_time. Fetch one more than the
                # number of statistics in the window, since all of them can be
                # missing a sum.
                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics,
                    self.hass,
                    len(window_stats) + 1,
                    statistic_id,
                    True,
                    {"sum"},
                )
                for last_stat in last_stats.get(statistic_id, []):
                    if (
                        last_stat["start"] < start_time.timestamp()
                        and last_stat["sum"] is not None
                    ):
                        statistic_sum = last_stat["sum"]
                        break
            if statistic_sum is None:
                # Expected for new installations or if the statistics were
                # cleared, e.g. from the developer tools
                statistic_sum = 0.0
            result[statistic_id] = statistic_sum
        return result


class SolarEdgeV2Coordinator(DataUpdateCoordinator[dict[str, Reading]]):
    """Power 2h, totals/counters 4h, lifetime daily, inventory/site weekly."""

    def __init__(
        self, hass: HomeAssistant, entry: SolarEdgeConfigEntry, oauth: OAuth2Session
    ) -> None:
        """Initialize durable cache and account-wide HA budget."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="SolarEdge Basic V2",
            update_interval=HOUR,
        )
        self.entry_id = entry.entry_id
        self.site_id = entry.data[CONF_SITE_ID]
        self.oauth = oauth
        self.budget = get_budget(hass)
        self.api = BasicMonitoring(
            async_get_clientsession(hass), self._access_token, self.budget.reserve
        )
        self.store: Store[dict[str, Any]] = Store(
            hass, 1, f"solaredge.v2.{entry.entry_id}"
        )
        self.state: dict = {
            "calls": [],
            "next_poll": 0,
            "failures": 0,
            "readings": {},
            "failed": False,
            "due": {},
            "periods": {},
            "metadata": entry.data.get("site_metadata", {}),
            "inventory": None,
        }

    async def _access_token(self) -> str:
        await self.oauth.async_ensure_token_valid()
        return self.oauth.token["access_token"]

    @override
    async def _async_setup(self) -> None:
        if saved := await self.store.async_load():
            if "due" not in saved:
                await self.budget.import_legacy(self.entry_id, saved["calls"])
            self.state.update(saved)
            if any(
                ("_battery_" in name or name.startswith("storage_"))
                and (item["value"] is not None or name in self.state["periods"])
                for name, item in self.state["readings"].items()
            ) and not any(
                device.get("active", True)
                for device in (self.state["inventory"] or {}).get("batteries", [])
            ):
                self._invalidate_storage(dt_util.utcnow())
                await self.store.async_save(self.state)

    def _cached(self) -> dict[str, Reading]:
        now = dt_util.utcnow()
        result = {}
        zone = self.state["metadata"].get("timezone")
        active = {
            device["serialNumber"]
            for device in (self.state["inventory"] or {}).get("batteries", [])
            if device.get("active", True)
        }
        for key, item in self.state["readings"].items():
            timestamp = datetime.fromisoformat(item["timestamp"])
            value = item["value"]
            if (key.startswith("storage_") and not active) or (
                "_battery_" in key
                and not any(key.startswith(f"{serial}_battery_") for serial in active)
            ):
                value = None
            period = PERIODS.get(key, "day" if "_battery_" in key else None)
            if period and (
                not zone
                or self.state["periods"].get(key)
                != period_start(now, zone, period).isoformat()
            ):
                value = None
            if (
                timestamp > now
                or (key == "average_power" and now - timestamp > HOUR * 4)
                or (key == "lifetime_energy" and now - timestamp > HOUR * 48)
            ):
                value = None
            result[key] = Reading(value, timestamp)
        return result

    def _save_readings(self, readings: dict[str, Reading], now: datetime) -> None:
        zone = self.state["metadata"].get("timezone")
        for key, reading in readings.items():
            self.state["readings"][key] = {
                "value": reading.value,
                "timestamp": reading.timestamp.isoformat(),
            }
            period = PERIODS.get(key, "day" if "_battery_" in key else None)
            if period and zone:
                self.state["periods"][key] = period_start(now, zone, period).isoformat()

    def _invalidate_storage(self, now: datetime) -> None:
        """Drop dependent values/observation times without deleting entities."""
        names = {"storage_charge_energy", "storage_discharge_energy"}
        names.update(name for name in self.state["readings"] if "_battery_" in name)
        for name in names:
            self.state["readings"][name] = {"value": None, "timestamp": now.isoformat()}
            self.state["periods"].pop(name, None)

    async def _read_job(self, key: str, now: datetime) -> dict[str, Reading]:
        """Fetch one bounded capability group independently."""
        readings = {}
        if key == "lifetime":
            readings["lifetime_energy"] = await self.api.lifetime_energy(self.site_id)
        elif key == "power":
            readings["average_power"] = await self.api.power(self.site_id, now)
        elif key == "metadata":
            metadata = await self.api.site(self.site_id)
            if str(metadata.get("siteId")) != self.site_id:
                raise SolarEdgeV2Error("Site mismatch")
            self.state["metadata"] = safe_metadata(metadata)
        elif key == "inventory":
            inventory = await self.api.inventory(self.site_id)
            if inventory != self.state["inventory"]:
                self._invalidate_storage(now)
            self.state["inventory"] = inventory
        elif key == "storage":
            self._invalidate_storage(now)
            inventory = self.state["inventory"]
            serials = [
                device["serialNumber"]
                for device in (inventory or {}).get("batteries", [])
                if device.get("active", True)
            ]
            if not serials or not (zone := self.state["metadata"].get("timezone")):
                self._invalidate_storage(now)
            else:
                try:
                    readings = await self.api.storage_daily(
                        self.site_id, now, zone, serials
                    )
                except InvalidResponseError:
                    # Valid new membership waits for the normal inventory cadence;
                    # malformed counters also fail closed, only for storage. Neither
                    # is authorization/quota failure or grounds for extra requests.
                    self._invalidate_storage(now)
        elif zone := self.state["metadata"].get("timezone"):
            if key in ("day", "month", "year"):
                readings = await self.api.overview(self.site_id, now, zone, key)
        return readings

    @override
    async def _async_update_data(self) -> dict[str, Reading]:
        now = dt_util.utcnow()
        timestamp = now.timestamp()
        if timestamp < self.state["next_poll"]:
            if self.state["failed"] or not self.state["readings"]:
                raise UpdateFailed("SolarEdge polling paused; quota/backoff preserved")
            return self._cached()
        calls = [t for t in self.state["calls"] if t > (now - WINDOW).timestamp()]
        due = self.state["due"]
        jobs = [
            ("lifetime", 24),
            ("power", 2),
            ("metadata", 168),
            ("inventory", 168),
            ("day", 4),
            ("month", 4),
            ("year", 4),
            ("storage", 4),
        ]
        jobs = [(key, hours) for key, hours in jobs if timestamp >= due.get(key, 0)]
        self.state.pop("auth_failed_jobs", None)
        if len(calls) >= MAX_CALLS or len(calls) + len(jobs) > MAX_CALLS:
            self.state.update(
                calls=calls, failed=True, next_poll=calls[0] + WINDOW.total_seconds()
            )
            await self.store.async_save(self.state)
            raise UpdateFailed("SolarEdge local rolling credit reserve exhausted")
        # Reserve full batch/cadences before I/O; global ledger additionally counts
        # each actual request, setup validation and token refresh conservatively.
        self.state.update(
            calls=[*calls, *([timestamp] * len(jobs))],
            next_poll=(now + HOUR * 2).timestamp(),
            failed=True,
        )
        # Until a job completes, persist only its retry deadline (the pre-I/O
        # pause), so an abrupt stop can never skip an unrequested job for a cadence.
        for key, _ in jobs:
            due[key] = self.state["next_poll"]
        await self.store.async_save(self.state)
        # A job advances to its normal cadence only once it completes, and that
        # completion is saved; failed or unattempted jobs keep a retry deadline.
        completed: set[str] = set()

        def unfinished() -> list[str]:
            return [key for key, _ in jobs if key not in completed]

        try:
            for key, hours in jobs:
                try:
                    readings = await self._read_job(key, now)
                    self.state.setdefault("permissions", {}).pop(key, None)
                except PermissionDeniedError:
                    # An older SITE_DATA-only grant may lack DEVICE_DATA. Do not
                    # lose valid production readings or turn scope failure into reauth.
                    self.state.setdefault("permissions", {})[key] = "denied"
                    if key == "inventory":
                        self.state["inventory"] = None
                        self._invalidate_storage(now)
                    affected = {
                        "lifetime": {"lifetime_energy"},
                        "power": {"average_power"},
                    }
                    for name in list(self.state["readings"]):
                        if (
                            name in affected.get(key, set())
                            or PERIODS.get(name) == key
                            or (
                                key == "storage"
                                and ("_battery_" in name or name.startswith("storage_"))
                            )
                        ):
                            self.state["readings"][name]["value"] = None
                    due[key] = (now + HOUR * hours).timestamp()
                    completed.add(key)
                    await self.store.async_save(self.state)
                    continue
                self._save_readings(readings, now)
                due[key] = (now + HOUR * hours).timestamp()
                completed.add(key)
                await self.store.async_save(self.state)
        except AuthenticationError, OAuth2TokenRequestReauthError:
            self.state["auth_failed_jobs"] = unfinished()
            for key in unfinished():
                due[key] = self.state["next_poll"]
            await self.store.async_save(self.state)
            raise ConfigEntryAuthFailed(
                "SolarEdge authorization must be renewed"
            ) from None
        except RateLimitError as err:
            if provider := err.http_status == 429:
                # Only an actual provider response is new account-wide evidence.
                await self.budget.pause(err)
                self.state["quota"] = err.quota
                self.state["quota_kind"] = (
                    "monthly" if err.monthly_exhausted else "throughput_or_unknown"
                )
            # A local refusal waits only for its remaining shared/local deadline,
            # measured from the refusal; it never extends or resets that deadline.
            self.state["next_poll"] = retry_deadline(
                err.retry_after,
                now if provider else dt_util.utcnow(),
                provider=provider,
            ).timestamp()
            for key in unfinished():
                due[key] = self.state["next_poll"]
            await self.store.async_save(self.state)
            raise UpdateFailed("SolarEdge quota exceeded; polling paused") from None
        except (
            SolarEdgeV2Error,
            OAuth2TokenRequestConnectionError,
            OAuth2TokenRequestError,
        ):
            self.state["failures"] += 1
            self.state["next_poll"] = (
                now + HOUR * min(24, 2 ** min(5, self.state["failures"] - 1))
            ).timestamp()
            for key in unfinished():
                due[key] = self.state["next_poll"]
            await self.store.async_save(self.state)
            raise UpdateFailed("SolarEdge read failed; polling backed off") from None
        except BaseException:
            # Cancellation or an unexpected error: keep the pre-I/O pause and
            # reservations, and retry unfinished jobs then instead of a full cadence.
            for key in unfinished():
                due[key] = self.state["next_poll"]
            self.hass.async_create_task(
                self.store.async_save(self.state), "SolarEdge V2 schedule save"
            )
            raise
        self.state.update(failures=0, failed=False)
        await self.store.async_save(self.state)
        return self._cached()
