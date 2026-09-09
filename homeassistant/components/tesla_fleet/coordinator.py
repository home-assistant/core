"""Tesla Fleet Data Coordinator."""

from asyncio import Task, shield
from datetime import datetime, timedelta
from time import time
from typing import TYPE_CHECKING, Any, override

from aiohttp import ClientError
from tesla_fleet_api.const import TeslaEnergyPeriod, VehicleDataEndpoint
from tesla_fleet_api.exceptions import (
    InternalServerError,
    InvalidToken,
    LoginRequired,
    NotFound,
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
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import CONF_TOKEN, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

if TYPE_CHECKING:
    from . import TeslaFleetConfigEntry

from .const import (
    DOMAIN,
    ENERGY_HISTORY_FIELDS,
    LOGGER,
    TeslaFleetState,
    build_statistic_id,
)
from .storage import EnergyHistoryStore

VEHICLE_INTERVAL_SECONDS = 600
VEHICLE_INTERVAL = timedelta(seconds=VEHICLE_INTERVAL_SECONDS)
VEHICLE_WAIT_SECONDS = 900
VEHICLE_WAIT = timedelta(seconds=VEHICLE_WAIT_SECONDS)
VEHICLE_STUCK_SECONDS = 1200

ENERGY_INTERVAL_SECONDS = 60
ENERGY_INTERVAL = timedelta(seconds=ENERGY_INTERVAL_SECONDS)
ENERGY_HISTORY_INTERVAL = timedelta(minutes=5)


def _stale_site_info_error(err: BaseException | None) -> TeslaFleetError | None:
    """Return the stale site_info error from an exception cause chain."""
    while err is not None:
        if isinstance(err, TeslaFleetError) and _is_stale_site_info_error(err):
            return err
        err = err.__cause__
    return None


def _is_stale_site_info_error(err: TeslaFleetError) -> bool:
    """Return whether a Tesla API site_info error indicates a stale energy site."""
    if isinstance(err, NotFound):
        return True
    if not isinstance(err, InternalServerError) or not isinstance(err.data, dict):
        return False
    return (
        "response" in err.data
        and err.data["response"] is None
        and err.data.get("error") == "upstream internal error"
    )


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
) -> dict[str, StatisticData]:
    """Return the latest long-term statistics for each statistic ID."""
    return {
        statistic_id: StatisticData(
            start=dt_util.utc_from_timestamp(stats[0]["start"]),
            state=stats[0]["state"] or 0.0,
            sum=stats[0]["sum"] or 0.0,
        )
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
    samples: dict[datetime, dict[str, Any]] = {}

    for period in time_series:
        timestamp_str = period.get("timestamp")
        if not timestamp_str:
            continue

        parsed_time = dt_util.parse_datetime(timestamp_str)
        if parsed_time is None:
            continue

        samples.setdefault(dt_util.as_utc(parsed_time), {}).update(period)

    hourly_periods: dict[datetime, dict[str, float]] = {}
    for timestamp, period in samples.items():
        start = timestamp.replace(minute=0, second=0, microsecond=0)
        hour_values = hourly_periods.setdefault(start, {})

        for key in ENERGY_HISTORY_FIELDS:
            if (value := period.get(key)) is None:
                continue
            hour_values[key] = hour_values.get(key, 0.0) + float(value)

    return sorted(hourly_periods.items())


def _parse_energy_history(
    response: Any,
) -> tuple[dict[str, Any], datetime]:
    """Validate an energy history response and its first timestamp."""
    if (
        not isinstance(response, dict)
        or not isinstance((data := response.get("response")), dict)
        or not isinstance((time_series := data.get("time_series")), list)
        or not time_series
        or not isinstance((first_period := time_series[0]), dict)
        or not isinstance((timestamp := first_period.get("timestamp")), str)
        or (period_start := dt_util.parse_datetime(timestamp)) is None
        or period_start.tzinfo is None
    ):
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_data",
        )
    return data, period_start


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
    last_active: float
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
        self.last_active = time()
        self.endpoints = (
            ENDPOINTS
            if location
            else [ep for ep in ENDPOINTS if ep != VehicleDataEndpoint.LOCATION_DATA]
        )

    @override
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
                self.last_active = time()
            else:
                elapsed = time() - self.last_active
                if elapsed > VEHICLE_STUCK_SECONDS:
                    # Vehicle didn't sleep, try again in 15 minutes
                    self.last_active = time()
                elif elapsed > VEHICLE_WAIT_SECONDS:
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

    @override
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
    """Manage fetching energy site history from the Tesla Fleet API."""

    config_entry: TeslaFleetConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TeslaFleetConfigEntry,
        api: EnergySite,
        site_name: str,
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
        self.site_name = site_name
        self.data = {}
        self.updated_once = False
        self._statistics_task: Task[None] | None = None
        self._statistics_failed = False
        self._history_store = EnergyHistoryStore(
            hass, config_entry.entry_id, api.energy_site_id
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update energy site history data using Tesla Fleet API."""
        self.update_interval = ENERGY_HISTORY_INTERVAL

        try:
            response = await self.api.energy_history(TeslaEnergyPeriod.DAY)
        except RateLimited as e:
            if self._statistics_task is not None:
                self._statistics_task.cancel()
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

        data, period_start = _parse_energy_history(response)
        time_series: list[dict[str, Any]] = data["time_series"]

        output: dict[str, Any] = dict.fromkeys(ENERGY_HISTORY_FIELDS, None)
        for period in time_series:
            for key in ENERGY_HISTORY_FIELDS:
                if key in period:
                    if output[key] is None:
                        output[key] = period[key]
                    else:
                        output[key] += period[key]

        output["_period_start"] = period_start

        if self._statistics_task is None or self._statistics_task.done():
            self._statistics_task = self.config_entry.async_create_background_task(
                self.hass,
                self._async_import_statistics(data, period_start),
                f"{self.name} statistics",
            )
            self._statistics_task.add_done_callback(self._statistics_done)

        self.updated_once = True
        return output

    @callback
    def _statistics_done(self, task: Task[None]) -> None:
        """Report unexpected import failures; cancellation is handled by the entry."""
        if not task.cancelled() and (error := task.exception()) is not None:
            LOGGER.error(
                "Unexpected statistics error for %s", self.name, exc_info=error
            )

    async def _async_import_statistics(
        self, data: dict[str, Any], period_start: datetime
    ) -> None:
        """Import history without blocking current-day sensor updates."""
        try:
            await self._async_backfill(data, period_start)
        except (TeslaFleetError, ClientError, TimeoutError, UpdateFailed) as err:
            if isinstance(err, LoginRequired):
                self.config_entry.async_start_reauth(self.hass)
            elif isinstance(err, (InvalidToken, OAuthExpired)):
                _invalidate_access_token(self.hass, self.config_entry)
            elif (
                isinstance(err, RateLimited)
                and isinstance(err.data, dict)
                and "after" in err.data
            ):
                self.update_interval = timedelta(seconds=int(err.data["after"]))
                if self._listeners:
                    self._schedule_refresh()
            if not self._statistics_failed:
                LOGGER.warning(
                    "Unable to import statistics for %s: %s",
                    self.name,
                    str(err) or type(err).__name__,
                )
            self._statistics_failed = True
        else:
            if self._statistics_failed:
                LOGGER.info("Statistics import recovered for %s", self.name)
            self._statistics_failed = False

    async def _async_backfill(
        self, data: dict[str, Any], period_start: datetime
    ) -> None:
        """Stream daily history from the last recorded hour through today."""
        if (
            not isinstance((time_zone := data.get("installation_time_zone")), str)
            or not time_zone
        ):
            raise UpdateFailed("Energy history did not include the site's timezone")
        if (site_time_zone := await dt_util.async_get_time_zone(time_zone)) is None:
            raise UpdateFailed("Energy history included an unknown site timezone")
        today = period_start.astimezone(site_time_zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        site_id = self.api.energy_site_id
        recorder = get_instance(self.hass)
        statistic_ids = [
            build_statistic_id(site_id, key) for key in ENERGY_HISTORY_FIELDS
        ]

        last_stats = await recorder.async_add_executor_job(
            _get_last_statistics_for_statistic_ids,
            self.hass,
            statistic_ids,
        )

        first_run_start = dt_util.as_utc(today).replace(
            minute=0, second=0, microsecond=0
        )
        start = min(
            (stat["start"] for stat in last_stats.values()),
            default=dt_util.as_utc(today),
        )
        if last_stats and (
            checkpoint := await self._history_store.async_get_start(last_stats)
        ):
            start = max(start, checkpoint)
        day = start.astimezone(site_time_zone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        window_start = dt_util.as_utc(day)
        previous_day: list[dict[str, Any]] = []
        while day <= today:
            next_day = day + timedelta(days=1)
            if day < today:
                response = await self.api.energy_history(
                    TeslaEnergyPeriod.DAY,
                    end_date=(next_day - timedelta(seconds=1)).isoformat(),
                )
                history, history_start = _parse_energy_history(response)
                if history_start.astimezone(site_time_zone).date() != day.date():
                    raise UpdateFailed("Energy history did not match the requested day")
                # Leave the boundary hour for the next day's overlapping window.
                window_end = dt_util.as_utc(next_day).replace(
                    minute=0, second=0, microsecond=0
                )
            else:
                history, window_end = data, None
            last_hour = self._add_statistics(
                [*previous_day, *history["time_series"]],
                last_stats,
                window_start,
                window_end,
                first_run_start,
            )
            await recorder.async_block_till_done()
            if last_stats:
                # Finish the write before unload can remove the checkpoint.
                await shield(
                    self.config_entry.async_create_task(
                        self.hass,
                        self._history_store.async_set_start(
                            window_end - timedelta(hours=1)
                            if window_end
                            else last_hour,
                            last_stats,
                        ),
                        f"{self.name} checkpoint",
                    )
                )
            previous_day = history["time_series"]
            window_start = dt_util.as_utc(day)
            day = next_day

    @callback
    def _add_statistics(
        self,
        time_series: list[dict[str, Any]],
        last_stats: dict[str, StatisticData],
        window_start: datetime,
        window_end: datetime | None,
        first_run_start: datetime,
    ) -> datetime:
        """Write complete windows and carry their totals into the next day."""
        hourly_periods = _aggregate_energy_history_by_hour(time_series)
        for key in ENERGY_HISTORY_FIELDS:
            statistic_id = build_statistic_id(self.api.energy_site_id, key)
            latest = last_stats.get(statistic_id)
            running_sum = latest["sum"] if latest else 0.0
            field_start = (
                max(latest["start"], window_start) if latest else first_run_start
            )
            statistics: list[StatisticData] = []
            for start, hour_values in hourly_periods:
                if start < field_start or (
                    window_end is not None and start >= window_end
                ):
                    continue

                if (state := hour_values.get(key)) is None:
                    continue

                if latest and start == latest["start"]:
                    running_sum -= latest["state"]
                running_sum += state

                statistics.append(
                    StatisticData(start=start, state=state, sum=running_sum)
                )

            if statistics:
                metadata = StatisticMetaData(
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=f"{self.site_name} {key.replace('_', ' ')}",
                    source=DOMAIN,
                    statistic_id=statistic_id,
                    unit_class=EnergyConverter.UNIT_CLASS,
                    unit_of_measurement=UnitOfEnergy.WATT_HOUR,
                )
                async_add_external_statistics(self.hass, metadata, statistics)
                last_stats[statistic_id] = statistics[-1]
        return hourly_periods[-1][0]


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

    @override
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
