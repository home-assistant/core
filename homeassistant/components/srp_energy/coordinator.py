"""DataUpdateCoordinator for the srp_energy integration."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from srpenergy.client import SrpEnergyClient

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.unit_conversion import EnergyConverter

from .const import (
    CONF_IS_TOU,
    DOMAIN,
    LOGGER,
    MIN_TIME_BETWEEN_UPDATES,
    PHOENIX_TIME_ZONE,
)

TIMEOUT = 10
PHOENIX_ZONE_INFO = dt_util.get_time_zone(PHOENIX_TIME_ZONE)

type SRPEnergyConfigEntry = ConfigEntry[SRPEnergyDataUpdateCoordinator]

# SRP finalizes yesterday's hourly data by approximately this hour (Phoenix time).
# Polling after this point until the next midnight is unnecessary.
DATA_COMPLETE_HOUR = 6

type HourlyUsageTuple = tuple[
    str, str, str, float, float
]  # (date, time, iso_timestamp, kwh, cost)


@dataclass(frozen=True, kw_only=True)
class Usage:
    """Hourly energy usage data."""

    start_time: datetime
    end_time: datetime
    kwh: float = 0.0
    cost: float = 0.0

    @staticmethod
    def from_tuple(usage: HourlyUsageTuple) -> Usage | None:
        """Initialize Usage from a raw API tuple, or None if unparsable."""
        if not usage or len(usage) != 5:
            return None
        parsed = dt_util.parse_datetime(usage[2])
        if parsed is None:
            return None
        try:
            kwh = float(usage[3])
            cost = float(usage[4])
        except TypeError, ValueError:
            return None
        start_time = (
            parsed.replace(tzinfo=PHOENIX_ZONE_INFO)
            if parsed.tzinfo is None
            else parsed.astimezone(PHOENIX_ZONE_INFO)
        )
        return Usage(
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            kwh=kwh,
            cost=cost,
        )


class SRPEnergyDataUpdateCoordinator(DataUpdateCoordinator[float]):
    """A srp_energy Data Update Coordinator."""

    config_entry: SRPEnergyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SRPEnergyConfigEntry,
        client: SrpEnergyClient,
    ) -> None:
        """Initialize the srp_energy data coordinator."""
        self._client = client
        self._is_time_of_use = config_entry.data[CONF_IS_TOU]
        self._data_complete_until: datetime | None = None
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    async def _async_update_data(self) -> float:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        LOGGER.debug("async_update_data enter")
        now = dt_util.now(PHOENIX_ZONE_INFO)

        # SRP finalizes yesterday's data by DATA_COMPLETE_HOUR. Once we've
        # confirmed completeness, skip the API call until the next midnight
        # when a new day's data becomes available.
        if self._data_complete_until and now < self._data_complete_until:
            LOGGER.debug(
                "Data is complete until %s, skipping fetch", self._data_complete_until
            )
            return self.data or 0.0

        # Because SRP provides hourly usage/cost for the previous day we need to
        # insert data into statistics ourselves.
        await self._insert_statistics()

        # Fetch last 24 hours of srp_energy data, but most recent could be almost
        # 24 hours ago, so we will use last 2 days and then take the last 24 hours
        end_date = now
        start_date = end_date - timedelta(days=2)
        hourly_usage = (await self._async_read_data(start_date, end_date))[-24:]

        LOGGER.debug(
            "async_update_data: Received %s record(s) from %s to %s",
            len(hourly_usage) if hourly_usage else "None",
            start_date,
            end_date,
        )

        previous_daily_usage = sum(float(hour.kwh) for hour in hourly_usage)

        LOGGER.debug(
            "async_update_data: previous_daily_usage %s",
            previous_daily_usage,
        )

        # Yesterday's data is finalized once it's past DATA_COMPLETE_HOUR.
        # Cache this so subsequent hourly ticks skip the API until next midnight.
        if now.hour >= DATA_COMPLETE_HOUR:
            next_midnight = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            self._data_complete_until = next_midnight
            LOGGER.debug(
                "Yesterday's data is complete. Next fetch after %s", next_midnight
            )

        return previous_daily_usage

    async def _insert_statistics(self) -> None:
        """Insert SRP statistics."""
        id_prefix = slugify(f"{self.config_entry.data[CONF_ID]}").lower()
        cost_statistic_id = f"{DOMAIN}:{id_prefix}_energy_cost"
        consumption_statistic_id = f"{DOMAIN}:{id_prefix}_energy_consumption"
        LOGGER.debug(
            "Updating Statistics for %s, and %s",
            cost_statistic_id,
            consumption_statistic_id,
        )
        name_prefix = f"SRP {self.config_entry.title}"
        cost_metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{name_prefix} electric cost",
            source=DOMAIN,
            statistic_id=cost_statistic_id,
            unit_class=None,
            unit_of_measurement=None,
        )

        consumption_metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{name_prefix} electric consumption",
            source=DOMAIN,
            statistic_id=consumption_statistic_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        # Get the last 2 statistics we have recorded for both consumption and
        # cost. We will use the oldest one as the baseline for the sum and
        # re-import the data after it. The last non-zero reported statistic
        # from SRP has potential to get updated as they fill out more data.
        last_stat, last_cost_stat = await asyncio.gather(
            get_instance(self.hass).async_add_executor_job(
                get_last_statistics,
                self.hass,
                2,
                consumption_statistic_id,
                True,
                {"sum"},
            ),
            get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 2, cost_statistic_id, True, {"sum"}
            ),
        )
        LOGGER.debug("Last statistics: %s", last_stat)
        if not last_stat:
            LOGGER.debug("Updating statistic for the first time")
            start_date = (dt_util.now(PHOENIX_ZONE_INFO) - timedelta(days=30)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            hourly_usage = await self._async_read_data(start_date=start_date)
            cost_sum = 0.0
            consumption_sum = 0.0
            last_stats_time = None
        else:
            start_date = datetime.fromtimestamp(
                last_stat[consumption_statistic_id][-1]["start"], PHOENIX_ZONE_INFO
            )
            LOGGER.debug(
                "Last statistics for %s at %s", consumption_statistic_id, start_date
            )
            hourly_usage = await self._async_read_data(start_date=start_date)
            if not hourly_usage:
                LOGGER.debug(
                    "No recent usage/cost data after %s. Skipping update", start_date
                )
                return
            start = hourly_usage[0].start_time
            LOGGER.debug("Getting statistics at: %s", start)
            for end in (start + timedelta(seconds=1), None):
                stats = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period,
                    self.hass,
                    start,
                    end,
                    {
                        cost_statistic_id,
                        consumption_statistic_id,
                    },
                    "hour",
                    None,
                    {"sum"},
                )
                if stats:
                    break
                if end:
                    LOGGER.debug(
                        "Not found. Trying to find the oldest statistic after %s",
                        start,
                    )

            def _safe_get_first(
                records: list[Any], key: str, default: float | None
            ) -> float | None:
                if records and records[0] and key in records[0]:
                    return float(records[0][key])
                return default

            if stats:
                LOGGER.debug("Statistics: %s", stats.get(cost_statistic_id, []))
                cost_sum = (
                    _safe_get_first(stats.get(cost_statistic_id, []), "sum", 0.0) or 0.0
                )
                consumption_sum = (
                    _safe_get_first(stats.get(consumption_statistic_id, []), "sum", 0.0)
                    or 0.0
                )
                last_stats_time = _safe_get_first(
                    stats.get(consumption_statistic_id, []), "start", None
                )
            else:
                # hourly_usage starts after the baseline stat period — SRP no
                # longer returns data that far back. Fall back to the most
                # recent known sums so we can continue the running total.
                LOGGER.debug(
                    "No statistics found at %s; using most recent known sums", start
                )
                cost_sum = (
                    _safe_get_first(
                        last_cost_stat.get(cost_statistic_id, []), "sum", 0.0
                    )
                    or 0.0
                )
                consumption_sum = (
                    _safe_get_first(
                        last_stat.get(consumption_statistic_id, []), "sum", 0.0
                    )
                    or 0.0
                )
                last_stats_time = _safe_get_first(
                    last_stat.get(consumption_statistic_id, []), "start", None
                )
            LOGGER.debug(
                "Last statistics for %s: Consumption sum: %s, Cost sum: %s, Last stat time: %s",
                consumption_statistic_id,
                consumption_sum,
                cost_sum,
                last_stats_time,
            )

        cost_statistics = []
        consumption_statistics = []

        # SRP pads incomplete/future hours with zeros at the tail. Strip those
        # trailing zeros so we don't create gaps for genuinely-zero hours earlier
        # in the dataset.
        last_nonzero = -1
        for i, usage in enumerate(hourly_usage):
            if usage.kwh != 0 or usage.cost != 0:
                last_nonzero = i
        hourly_usage = hourly_usage[: last_nonzero + 1]

        for usage in hourly_usage:
            start = usage.start_time
            LOGGER.debug(
                "Processing usage data for %s. Last stat time: %s. Usage: %s, Cost: %s",
                start.timestamp(),
                last_stats_time,
                usage.kwh,
                usage.cost,
            )

            if last_stats_time is not None and start.timestamp() <= last_stats_time:
                continue

            cost_state = max(0, usage.cost)
            consumption_state = max(0, usage.kwh)

            cost_sum += cost_state
            consumption_sum += consumption_state

            cost_statistics.append(
                StatisticData(start=start, state=cost_state, sum=cost_sum)
            )
            consumption_statistics.append(
                StatisticData(start=start, state=consumption_state, sum=consumption_sum)
            )

        LOGGER.debug(
            "Adding %s statistics for %s",
            len(cost_statistics),
            cost_statistic_id,
        )
        async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
        LOGGER.debug(
            "Adding %s statistics for %s",
            len(consumption_statistics),
            consumption_statistic_id,
        )
        async_add_external_statistics(
            self.hass, consumption_metadata, consumption_statistics
        )

    async def _async_read_data(
        self, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[Usage]:
        """Read data from srp_energy client.

        There are some limitations here. The current api *client* only knows how to fetch the hourly usage data.
        The hourly data for SRP is only available for the last month (30 days?).
        The SRP api does provide daily usage for the last 12 months and monthly usage for the last 3 years,
        however the api client will need to be updated to support these additional timeframes.
        """
        try:
            async with asyncio.timeout(TIMEOUT):
                end_date = end_date or dt_util.now(PHOENIX_ZONE_INFO)
                start_date = start_date or (end_date - timedelta(days=31)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                results = [
                    u
                    for u in map(
                        Usage.from_tuple,
                        await self.hass.async_add_executor_job(
                            self._client.usage,
                            start_date,
                            end_date,
                            self._is_time_of_use,
                        ),
                    )
                    if u is not None
                ]
                # Filter out any results that are outside the requested date range because the SRP API only uses dates,
                # not times, so the actual data we receive may be outside the requested range.
                results = [
                    result
                    for result in results
                    if result.start_time >= start_date and result.end_time <= end_date
                ]
                LOGGER.debug(
                    "async_read_data: Received %s record(s) from %s to %s",
                    len(results) if results else "None",
                    start_date,
                    end_date,
                )
                return results
        except (ValueError, TypeError) as err:
            LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
