"""Coordinator to handle Opower connections."""

from datetime import datetime, timedelta
from enum import Enum
import logging
from types import MappingProxyType
from typing import Any, cast

from opower import (
    Account,
    AggregateType,
    CostRead,
    Forecast,
    InvalidAuth,
    MeterType,
    Opower,
    ReadResolution,
)

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_TOTP_SECRET, CONF_UTILITY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class StatisticType(Enum):
    """Statistic types included."""

    COST = "COST"
    CONSUMPTION = "CONSUMPTION"

    def __str__(self) -> str:
        """Return the value of the enum."""
        return self.value


class OpowerCoordinator(DataUpdateCoordinator[dict[str, Forecast]]):
    """Handle fetching Opower data, updating sensors and inserting statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: MappingProxyType[str, Any],
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            name="Opower",
            # Data is updated daily on Opower.
            # Refresh every 12h to be at most 12h behind.
            update_interval=timedelta(hours=12),
        )
        self.api = Opower(
            aiohttp_client.async_get_clientsession(hass),
            entry_data[CONF_UTILITY],
            entry_data[CONF_USERNAME],
            entry_data[CONF_PASSWORD],
            entry_data.get(CONF_TOTP_SECRET),
        )

        @callback
        def _dummy_listener() -> None:
            pass

        # Force the coordinator to periodically update by registering at least one listener.
        # Needed when the _async_update_data below returns {} for utilities that don't provide
        # forecast, which results to no sensors added, no registered listeners, and thus
        # _async_update_data not periodically getting called which is needed for _insert_statistics.
        self.async_add_listener(_dummy_listener)

    async def _async_update_data(
        self,
    ) -> dict[str, Forecast]:
        """Fetch data from API endpoint."""
        try:
            # Login expires after a few minutes.
            # Given the infrequent updating (every 12h)
            # assume previous session has expired and re-login.
            await self.api.async_login()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        forecasts: list[Forecast] = await self.api.async_get_forecast()
        _LOGGER.debug("Updating sensor data with: %s", forecasts)
        # Because Opower provides historical usage/cost with a delay of a couple of days
        # we need to insert data into statistics.
        await self._insert_statistics()
        return {forecast.account.utility_account_id: forecast for forecast in forecasts}

    async def _insert_statistics(self) -> None:
        """Insert Opower statistics."""
        for account in await self.api.async_get_accounts():
            id_prefix = "_".join(
                (
                    self.api.utility.subdomain(),
                    account.meter_type.name.lower(),
                    # Some utilities like AEP have "-" in their account id.
                    # Replace it with "_" to avoid "Invalid statistic_id"
                    account.utility_account_id.replace("-", "_").lower(),
                )
            )
            cost_statistic_id = f"{DOMAIN}:{id_prefix}_energy_cost"
            consumption_statistic_id = f"{DOMAIN}:{id_prefix}_energy_consumption"
            _LOGGER.debug(
                "Updating Statistics for %s and %s",
                cost_statistic_id,
                consumption_statistic_id,
            )

            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
            )
            if not last_stat:
                _LOGGER.debug("Updating statistic for the first time")
                cost_reads, cost_reads_billing = await self._async_get_cost_reads(
                    account, self.api.utility.timezone()
                )
                cost_sum = 0.0
                consumption_sum = 0.0
                last_stats_time = None
                last_stats_time_billing = None
            else:
                cost_reads, cost_reads_billing = await self._async_get_cost_reads(
                    account,
                    self.api.utility.timezone(),
                    last_stat[consumption_statistic_id][0]["start"],
                )
                if not cost_reads:
                    _LOGGER.debug("No recent usage/cost data. Skipping update")
                    continue
                start = cost_reads[0].start_time
                _LOGGER.debug("Getting statistics at: %s", start)
                # In the common case there should be a previous statistic at start time
                # so we only need to fetch one statistic. If there isn't any, fetch all.
                for end in (start + timedelta(seconds=1), None):
                    stats = await get_instance(self.hass).async_add_executor_job(
                        statistics_during_period,
                        self.hass,
                        start,
                        end,
                        {cost_statistic_id, consumption_statistic_id},
                        "hour",
                        None,
                        {"sum"},
                    )
                    if stats:
                        break
                    if end:
                        _LOGGER.debug(
                            "Not found. Trying to find the oldest statistic after %s",
                            start,
                        )
                # We are in this code path only if get_last_statistics found a stat
                # so statistics_during_period should also have found at least one.
                assert stats
                cost_sum = cast(float, stats[cost_statistic_id][0]["sum"])
                consumption_sum = cast(float, stats[consumption_statistic_id][0]["sum"])
                last_stats_time = stats[consumption_statistic_id][0]["start"]
                if cost_reads_billing:
                    start = cost_reads_billing[0].start_time
                    _LOGGER.debug("Getting cost statistics at: %s", start)
                    # In the common case there should be a previous statistic at start time
                    # so we only need to fetch one statistic. If there isn't any, fetch all.
                    for end in (start + timedelta(seconds=1), None):
                        stats = await get_instance(self.hass).async_add_executor_job(
                            statistics_during_period,
                            self.hass,
                            start,
                            end,
                            {cost_statistic_id},
                            "hour",
                            None,
                            {"sum"},
                        )
                        if stats:
                            break
                        if end:
                            _LOGGER.debug(
                                "Not found. Trying to find the oldest statistic after %s",
                                start,
                            )
                    # We are in this code path only if get_last_statistics found a stat
                    # so statistics_during_period should also have found at least one.
                    assert stats
                    cost_sum = cast(float, stats[cost_statistic_id][0]["sum"])
                    last_stats_time_billing = stats[cost_statistic_id][0]["start"]

            await self._insert_statistics_cost_read(
                account,
                cost_statistic_id,
                consumption_statistic_id,
                cost_sum,
                consumption_sum,
                last_stats_time,
                cost_reads,
                [StatisticType.COST, StatisticType.CONSUMPTION]
                if not cost_reads_billing
                else [StatisticType.CONSUMPTION],
            )

            if cost_reads_billing:
                await self._insert_statistics_cost_read(
                    account,
                    cost_statistic_id,
                    consumption_statistic_id,
                    cost_sum,
                    consumption_sum,
                    last_stats_time_billing,
                    cost_reads_billing,
                    [StatisticType.COST],
                )

    async def _insert_statistics_cost_read(
        self,
        account: Account,
        cost_statistic_id: str,
        consumption_statistic_id: str,
        cost_sum: float,
        consumption_sum: float,
        last_stats_time: float | None,
        cost_reads: list[CostRead],
        statistic_types: list[StatisticType],
    ) -> None:
        """Insert Opower statistics for a single cost read list."""
        cost_statistics = []
        consumption_statistics = []

        for cost_read in cost_reads:
            start = cost_read.start_time
            if last_stats_time is not None and start.timestamp() <= last_stats_time:
                continue
            cost_sum += cost_read.provided_cost
            consumption_sum += cost_read.consumption

            if StatisticType.COST in statistic_types:
                cost_statistics.append(
                    StatisticData(
                        start=start, state=cost_read.provided_cost, sum=cost_sum
                    )
                )
            if StatisticType.CONSUMPTION in statistic_types:
                consumption_statistics.append(
                    StatisticData(
                        start=start, state=cost_read.consumption, sum=consumption_sum
                    )
                )

        name_prefix = (
            f"Opower {self.api.utility.subdomain()} "
            f"{account.meter_type.name.lower()} {account.utility_account_id}"
        )
        if StatisticType.COST in statistic_types:
            cost_metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"{name_prefix} cost",
                source=DOMAIN,
                statistic_id=cost_statistic_id,
                unit_of_measurement=None,
            )
        if StatisticType.CONSUMPTION in statistic_types:
            consumption_metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"{name_prefix} consumption",
                source=DOMAIN,
                statistic_id=consumption_statistic_id,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR
                if account.meter_type == MeterType.ELEC
                else UnitOfVolume.CENTUM_CUBIC_FEET,
            )

        if StatisticType.COST in statistic_types:
            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(cost_statistics),
                cost_statistic_id,
            )
            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
        if StatisticType.CONSUMPTION in statistic_types:
            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(consumption_statistics),
                consumption_statistic_id,
            )
            async_add_external_statistics(
                self.hass, consumption_metadata, consumption_statistics
            )

    async def _async_get_cost_reads(
        self, account: Account, time_zone_str: str, start_time: float | None = None
    ) -> tuple[list[CostRead], list[CostRead] | None]:
        """Get cost reads.

        If start_time is None, get cost reads since account activation,
        otherwise since start_time - 30 days to allow corrections in data from utilities

        We read at different resolutions depending on age:
        - month resolution for all years (since account activation)
        - day resolution for past 3 years (if account's read resolution supports it)
        - hour resolution for past 2 months (if account's read resolution supports it)
        """

        def _update_with_finer_cost_reads(
            cost_reads: list[CostRead], finer_cost_reads: list[CostRead]
        ) -> None:
            for i, cost_read in enumerate(cost_reads):
                for j, finer_cost_read in enumerate(finer_cost_reads):
                    if cost_read.start_time == finer_cost_read.start_time:
                        cost_reads[i:] = finer_cost_reads[j:]
                        return
                    if cost_read.end_time == finer_cost_read.start_time:
                        cost_reads[i + 1 :] = finer_cost_reads[j:]
                        return
                    if cost_read.end_time < finer_cost_read.start_time:
                        break
            cost_reads += finer_cost_reads

        def _check_is_cost_missing(
            cost_reads: list[CostRead], finer_cost_reads: list[CostRead]
        ) -> bool:
            if not cost_reads or not finer_cost_reads:
                return False
            sum_cost_reads = 0
            sum_finer_cost_reads = 0
            for _, cost_read in enumerate(cost_reads):
                # Skip to first bill read fully represented in fine reads
                if cost_read.start_time < finer_cost_reads[0].start_time:
                    continue
                sum_cost_reads += cost_read.provided_cost
            for _, finer_cost_read in enumerate(finer_cost_reads):
                # End if beyond rough cost read window
                if cost_reads[-1].end_time < finer_cost_read.start_time:
                    break
                sum_finer_cost_reads += finer_cost_read.provided_cost
            _LOGGER.debug(
                "Calculated cost sums rough: %s fine: %s",
                sum_cost_reads,
                sum_finer_cost_reads,
            )
            return sum_cost_reads > 0 and sum_finer_cost_reads == 0

        cost_reads_billing = None
        tz = await dt_util.async_get_time_zone(time_zone_str)
        if start_time is None:
            start = None
        else:
            start = datetime.fromtimestamp(start_time, tz=tz) - timedelta(days=30)
        end = dt_util.now(tz)
        _LOGGER.debug("Getting monthly cost reads: %s - %s", start, end)
        cost_reads = await self.api.async_get_cost_reads(
            account, AggregateType.BILL, start, end
        )
        _LOGGER.debug("Got %s monthly cost reads", len(cost_reads))
        if account.read_resolution == ReadResolution.BILLING:
            return cost_reads, None

        if start_time is None:
            start = end - timedelta(days=3 * 365)
        else:
            if cost_reads:
                start = cost_reads[0].start_time
            assert start
            start = max(start, end - timedelta(days=3 * 365))
        _LOGGER.debug("Getting daily cost reads: %s - %s", start, end)
        daily_cost_reads = await self.api.async_get_cost_reads(
            account, AggregateType.DAY, start, end
        )
        _LOGGER.debug("Got %s daily cost reads", len(daily_cost_reads))
        if _check_is_cost_missing(cost_reads, daily_cost_reads):
            _LOGGER.debug(
                "Daily data seems to be missing cost data, falling back to bill view for costs"
            )
            cost_reads_billing = cost_reads.copy()
        _update_with_finer_cost_reads(cost_reads, daily_cost_reads)
        if account.read_resolution == ReadResolution.DAY:
            return cost_reads, cost_reads_billing

        if start_time is None:
            start = end - timedelta(days=2 * 30)
        else:
            assert start
            start = max(start, end - timedelta(days=2 * 30))
        _LOGGER.debug("Getting hourly cost reads: %s - %s", start, end)
        hourly_cost_reads = await self.api.async_get_cost_reads(
            account, AggregateType.HOUR, start, end
        )
        _LOGGER.debug("Got %s hourly cost reads", len(hourly_cost_reads))
        if _check_is_cost_missing(daily_cost_reads, hourly_cost_reads):
            _LOGGER.debug(
                "Hourly data seems to be missing cost data, falling back to daily view for costs"
            )
            cost_reads_billing = daily_cost_reads.copy()
        _update_with_finer_cost_reads(cost_reads, hourly_cost_reads)
        _LOGGER.debug("Got %s cost reads", len(cost_reads))
        return cost_reads, cost_reads_billing
