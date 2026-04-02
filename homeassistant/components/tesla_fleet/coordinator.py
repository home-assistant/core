"""Tesla Fleet Data Coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from tesla_fleet_api.const import TeslaEnergyPeriod, VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    InvalidToken,
    LoginRequired,
    OAuthExpired,
    RateLimited,
    TeslaFleetError,
    VehicleOffline,
)
from tesla_fleet_api.tesla import EnergySite, VehicleFleet

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import CONF_TOKEN, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

if TYPE_CHECKING:
    from . import TeslaFleetConfigEntry

from .const import DOMAIN, ENERGY_HISTORY_FIELDS, LOGGER, TeslaFleetState

VEHICLE_INTERVAL_SECONDS = 600
VEHICLE_INTERVAL = timedelta(seconds=VEHICLE_INTERVAL_SECONDS)
VEHICLE_WAIT = timedelta(minutes=15)

ENERGY_INTERVAL_SECONDS = 60
ENERGY_INTERVAL = timedelta(seconds=ENERGY_INTERVAL_SECONDS)
ENERGY_HISTORY_INTERVAL = timedelta(minutes=5)

ENDPOINTS = [
    VehicleDataEndpoint.CHARGE_STATE,
    VehicleDataEndpoint.CLIMATE_STATE,
    VehicleDataEndpoint.DRIVE_STATE,
    VehicleDataEndpoint.VEHICLE_STATE,
    VehicleDataEndpoint.VEHICLE_CONFIG,
    VehicleDataEndpoint.LOCATION_DATA,
]


def _get_last_statistics_for_statistic_ids(
    hass: HomeAssistant,
    statistic_ids: list[str],
) -> dict[str, list[StatisticsRow]]:
    """Return the latest long-term statistics for each statistic ID."""
    return {
        statistic_id: stats
        for statistic_id in statistic_ids
        if (
            stats := get_last_statistics(
                hass,
                1,
                statistic_id,
                False,
                {"state", "sum"},
            ).get(statistic_id)
        )
    }


def _aggregate_energy_history_by_hour(
    time_series: list[dict[str, Any]],
) -> list[tuple[datetime, dict[str, float]]]:
    """Aggregate energy history samples into recorder-compatible hourly buckets."""
    hourly_periods: dict[datetime, dict[str, float]] = {}

    for period in time_series:
        timestamp_str = period.get("timestamp")
        if not timestamp_str:
            continue

        parsed_time = dt_util.parse_datetime(timestamp_str)
        if parsed_time is None:
            continue

        start = dt_util.as_utc(parsed_time).replace(minute=0, second=0, microsecond=0)
        hour_values = hourly_periods.setdefault(start, {})

        for key in ENERGY_HISTORY_FIELDS:
            if (value := period.get(key)) is None:
                continue
            hour_values[key] = hour_values.get(key, 0.0) + float(value)

    return sorted(hourly_periods.items())


def _invalidate_access_token(
    hass: HomeAssistant, config_entry: TeslaFleetConfigEntry
) -> None:
    """Invalidate the cached access token to force a refresh."""
    if (
        not (token_data := config_entry.data.get(CONF_TOKEN))
        or token_data.get("expires_at") == 0
    ):
        return

    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_TOKEN: {
                **token_data,
                "expires_at": 0,
            },
        },
    )


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

    config_entry: TeslaFleetConfigEntry
    updated_once: bool
    pre2021: bool
    last_active: datetime
    endpoints: list[VehicleDataEndpoint]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslaFleetConfigEntry,
        api: VehicleFleet,
        product: dict,
        location: bool,
    ) -> None:
        """Initialize TeslaFleet Vehicle Update Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Tesla Fleet Vehicle",
            update_interval=VEHICLE_INTERVAL,
        )
        self.api = api
        self.data = flatten(product)
        self.updated_once = False
        self.last_active = datetime.now()
        self.endpoints = (
            ENDPOINTS
            if location
            else [ep for ep in ENDPOINTS if ep != VehicleDataEndpoint.LOCATION_DATA]
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update vehicle data using TeslaFleet API."""

        try:
            # Check if the vehicle is awake using a free API call
            response = await self.api.vehicle()
            self.data["state"] = response["response"]["state"]

            if self.data["state"] != TeslaFleetState.ONLINE:
                return self.data

            response = await self.api.vehicle_data(endpoints=self.endpoints)
            data = response["response"]

        except VehicleOffline:
            self.data["state"] = TeslaFleetState.ASLEEP
            return self.data
        except RateLimited:
            LOGGER.warning(
                "%s rate limited, will skip refresh",
                self.name,
            )
            return self.data
        except (InvalidToken, OAuthExpired) as e:
            _invalidate_access_token(self.hass, self.config_entry)
            raise UpdateFailed(e.message) from e
        except LoginRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        self.update_interval = VEHICLE_INTERVAL

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

    config_entry: TeslaFleetConfigEntry
    updated_once: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslaFleetConfigEntry,
        api: EnergySite,
    ) -> None:
        """Initialize TeslaFleet Energy Site Live coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
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
            if isinstance(e.data, dict) and "after" in e.data:
                LOGGER.warning(
                    "%s rate limited, will retry in %s seconds",
                    self.name,
                    e.data["after"],
                )
                self.update_interval = timedelta(seconds=int(e.data["after"]))
            else:
                LOGGER.warning("%s rate limited, will skip refresh", self.name)
            return self.data
        except (InvalidToken, OAuthExpired) as e:
            _invalidate_access_token(self.hass, self.config_entry)
            raise UpdateFailed(e.message) from e
        except LoginRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        if not isinstance(data, dict):
            LOGGER.debug(
                "%s got unexpected live status response type: %s",
                self.name,
                type(data).__name__,
            )
            return self.data

        # Convert Wall Connectors from array to dict
        wall_connectors = data.get("wall_connectors")
        if not isinstance(wall_connectors, list):
            wall_connectors = []
        data["wall_connectors"] = {
            wc["din"]: wc
            for wc in wall_connectors
            if isinstance(wc, dict) and "din" in wc
        }

        self.updated_once = True
        return data


class TeslaFleetEnergySiteHistoryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site history import and export from the Tesla Fleet API."""

    config_entry: TeslaFleetConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslaFleetConfigEntry,
        api: EnergySite,
    ) -> None:
        """Initialize Tesla Fleet Energy Site History coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"Tesla Fleet Energy History {api.energy_site_id}",
            update_interval=ENERGY_HISTORY_INTERVAL,
        )
        self.api = api
        self.data = {}
        self.updated_once = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site history data using Tesla Fleet API."""
        try:
            response = await self.api.energy_history(TeslaEnergyPeriod.DAY)
        except RateLimited as e:
            if isinstance(e.data, dict) and "after" in e.data:
                LOGGER.warning(
                    "%s rate limited, will retry in %s seconds",
                    self.name,
                    e.data["after"],
                )
                self.update_interval = timedelta(seconds=int(e.data["after"]))
            else:
                LOGGER.warning("%s rate limited, will skip refresh", self.name)
            return self.data
        except (InvalidToken, OAuthExpired) as e:
            _invalidate_access_token(self.hass, self.config_entry)
            raise UpdateFailed(e.message) from e
        except LoginRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        if (
            not isinstance(response, dict)
            or not isinstance((data := response.get("response")), dict)
            or not isinstance((time_series := data.get("time_series")), list)
            or not time_series
            or not isinstance((first_period := time_series[0]), dict)
            or not isinstance((timestamp := first_period.get("timestamp")), str)
            or (period_start := dt_util.parse_datetime(timestamp)) is None
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_data",
            )

        # Insert external statistics with historical timestamps
        await self._insert_statistics(time_series)

        # Calculate daily sums for sensor entities
        output: dict[str, Any] = dict.fromkeys(ENERGY_HISTORY_FIELDS, None)
        for period in time_series:
            for key in ENERGY_HISTORY_FIELDS:
                if key in period:
                    if output[key] is None:
                        output[key] = period[key]
                    else:
                        output[key] += period[key]

        output["_period_start"] = period_start

        self.updated_once = True
        return output

    async def _insert_statistics(self, time_series: list[dict[str, Any]]) -> None:
        """Insert energy history statistics at their actual historical timestamps."""
        if not (hourly_periods := _aggregate_energy_history_by_hour(time_series)):
            return

        site_id = self.api.energy_site_id
        recorder = get_instance(self.hass)
        statistic_ids = [f"{DOMAIN}:{site_id}_{key}" for key in ENERGY_HISTORY_FIELDS]

        # Fetch all existing last statistics in a single executor call.
        try:
            last_stats = await recorder.async_add_executor_job(
                _get_last_statistics_for_statistic_ids,
                self.hass,
                statistic_ids,
            )
        except HomeAssistantError as err:
            LOGGER.warning(
                "Unable to fetch existing statistics for energy site %s: %s",
                site_id,
                err,
            )
            return

        for key in ENERGY_HISTORY_FIELDS:
            statistic_id = f"{DOMAIN}:{site_id}_{key}"
            metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"Tesla energy site {site_id} {key.replace('_', ' ')}",
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_class=EnergyConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            )
            existing_stats = last_stats.get(statistic_id)

            if not existing_stats:
                # First time - start from scratch
                LOGGER.debug(
                    "Inserting statistics for %s for the first time", statistic_id
                )
                last_stats_time = None
                running_sum = 0.0
            else:
                latest_stat = existing_stats[0]
                last_stats_time = latest_stat["start"]
                latest_sum = latest_stat.get("sum", 0.0) or 0.0
                if any(
                    start.timestamp() == last_stats_time and key in hour_values
                    for start, hour_values in hourly_periods
                ):
                    # Re-import the latest hour if new samples have appeared for it;
                    # recorder updates the existing row in place for the same start.
                    latest_state = latest_stat.get("state", 0.0) or 0.0
                    running_sum = latest_sum - latest_state
                else:
                    running_sum = latest_sum

            statistics: list[StatisticData] = []

            for start, hour_values in hourly_periods:
                start_ts = start.timestamp()
                if last_stats_time is not None and start_ts < last_stats_time:
                    continue

                if (state := hour_values.get(key)) is None:
                    continue

                running_sum += state

                statistics.append(
                    StatisticData(start=start, state=state, sum=running_sum)
                )

            if statistics:
                LOGGER.debug(
                    "Adding %s statistics for %s",
                    len(statistics),
                    statistic_id,
                )
                try:
                    async_add_external_statistics(self.hass, metadata, statistics)
                except HomeAssistantError as err:
                    LOGGER.warning(
                        "Unable to add external statistics for %s: %s",
                        statistic_id,
                        err,
                    )


class TeslaFleetEnergySiteInfoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching energy site info from the TeslaFleet API."""

    config_entry: TeslaFleetConfigEntry
    updated_once: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslaFleetConfigEntry,
        api: EnergySite,
        product: dict,
    ) -> None:
        """Initialize TeslaFleet Energy Info coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
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
            if isinstance(e.data, dict) and "after" in e.data:
                LOGGER.warning(
                    "%s rate limited, will retry in %s seconds",
                    self.name,
                    e.data["after"],
                )
                self.update_interval = timedelta(seconds=int(e.data["after"]))
            else:
                LOGGER.warning("%s rate limited, will skip refresh", self.name)
            return self.data
        except (InvalidToken, OAuthExpired) as e:
            _invalidate_access_token(self.hass, self.config_entry)
            raise UpdateFailed(e.message) from e
        except LoginRequired as e:
            raise ConfigEntryAuthFailed from e
        except TeslaFleetError as e:
            raise UpdateFailed(e.message) from e

        self.updated_once = True
        return flatten(data)
