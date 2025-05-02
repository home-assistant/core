"""Coordinator to handle Opower connections."""

from datetime import datetime, timedelta
import logging
from typing import Any, cast

from opower import (
    Account,
    AggregateType,
    CostRead,
    Forecast,
    MeterType,
    Opower,
    ReadResolution,
)
from opower.exceptions import ApiException, CannotConnect, InvalidAuth

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
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_TOTP_SECRET, CONF_UTILITY, DOMAIN

_LOGGER = logging.getLogger(__name__)

type OpowerConfigEntry = ConfigEntry[OpowerCoordinator]


class OpowerCoordinator(DataUpdateCoordinator[dict[str, Forecast]]):
    """Handle fetching Opower data, updating sensors and inserting statistics."""

    config_entry: OpowerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpowerConfigEntry,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Opower",
            # Data is updated daily on Opower.
            # Refresh every 12h to be at most 12h behind.
            update_interval=timedelta(hours=12),
        )
        self.api = Opower(
            aiohttp_client.async_get_clientsession(hass),
            config_entry.data[CONF_UTILITY],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data.get(CONF_TOTP_SECRET),
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
            _LOGGER.error("Error during login: %s", err)
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            _LOGGER.error("Error during login: %s", err)
            raise UpdateFailed(f"Error during login: {err}") from err
        try:
            forecasts: list[Forecast] = await self.api.async_get_forecast()
        except ApiException as err:
            _LOGGER.error("Error getting forecasts: %s", err)
            raise
        _LOGGER.debug("Updating sensor data with: %s", forecasts)
        # Because Opower provides historical usage/cost with a delay of a couple of days
        # we need to insert data into statistics.
        await self._insert_statistics()
        return {forecast.account.utility_account_id: forecast for forecast in forecasts}

    async def _insert_statistics(self) -> None:
        """Insert Opower statistics."""
        try:
            accounts = await self.api.async_get_accounts()
        except ApiException as err:
            _LOGGER.error("Error getting accounts: %s", err)
            raise
        for account in accounts:
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
            compensation_statistic_id = f"{DOMAIN}:{id_prefix}_energy_compensation"
            consumption_statistic_id = f"{DOMAIN}:{id_prefix}_energy_consumption"
            return_statistic_id = f"{DOMAIN}:{id_prefix}_energy_return"
            _LOGGER.debug(
                "Updating Statistics for %s, %s, %s, and %s",
                cost_statistic_id,
                compensation_statistic_id,
                consumption_statistic_id,
                return_statistic_id,
            )

            name_prefix = (
                f"Opower {self.api.utility.subdomain()} "
                f"{account.meter_type.name.lower()} {account.utility_account_id}"
            )
            cost_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} cost",
                source=DOMAIN,
                statistic_id=cost_statistic_id,
                unit_of_measurement=None,
            )
            compensation_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} compensation",
                source=DOMAIN,
                statistic_id=compensation_statistic_id,
                unit_of_measurement=None,
            )
            consumption_unit = (
                UnitOfEnergy.KILO_WATT_HOUR
                if account.meter_type == MeterType.ELEC
                else UnitOfVolume.CENTUM_CUBIC_FEET
            )
            consumption_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} consumption",
                source=DOMAIN,
                statistic_id=consumption_statistic_id,
                unit_of_measurement=consumption_unit,
            )
            return_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} return",
                source=DOMAIN,
                statistic_id=return_statistic_id,
                unit_of_measurement=consumption_unit,
            )

            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, consumption_statistic_id, True, set()
            )
            if not last_stat:
                _LOGGER.debug("Updating statistic for the first time")
                cost_reads = await self._async_get_cost_reads(
                    account, self.api.utility.timezone()
                )
                cost_sum = 0.0
                compensation_sum = 0.0
                consumption_sum = 0.0
                return_sum = 0.0
                last_stats_time = None
            else:
                await self._async_maybe_migrate_statistics(
                    account.utility_account_id,
                    {
                        cost_statistic_id: compensation_statistic_id,
                        consumption_statistic_id: return_statistic_id,
                    },
                    {
                        cost_statistic_id: cost_metadata,
                        compensation_statistic_id: compensation_metadata,
                        consumption_statistic_id: consumption_metadata,
                        return_statistic_id: return_metadata,
                    },
                )
                cost_reads = await self._async_get_cost_reads(
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
                        {
                            cost_statistic_id,
                            compensation_statistic_id,
                            consumption_statistic_id,
                            return_statistic_id,
                        },
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

                def _safe_get_sum(records: list[Any]) -> float:
                    if records and "sum" in records[0]:
                        return float(records[0]["sum"])
                    return 0.0

                cost_sum = _safe_get_sum(stats.get(cost_statistic_id, []))
                compensation_sum = _safe_get_sum(
                    stats.get(compensation_statistic_id, [])
                )
                consumption_sum = _safe_get_sum(stats.get(consumption_statistic_id, []))
                return_sum = _safe_get_sum(stats.get(return_statistic_id, []))
                last_stats_time = stats[consumption_statistic_id][0]["start"]

            cost_statistics = []
            compensation_statistics = []
            consumption_statistics = []
            return_statistics = []

            for cost_read in cost_reads:
                start = cost_read.start_time
                if last_stats_time is not None and start.timestamp() <= last_stats_time:
                    continue

                cost_state = max(0, cost_read.provided_cost)
                compensation_state = max(0, -cost_read.provided_cost)
                consumption_state = max(0, cost_read.consumption)
                return_state = max(0, -cost_read.consumption)

                cost_sum += cost_state
                compensation_sum += compensation_state
                consumption_sum += consumption_state
                return_sum += return_state

                cost_statistics.append(
                    StatisticData(start=start, state=cost_state, sum=cost_sum)
                )
                compensation_statistics.append(
                    StatisticData(
                        start=start, state=compensation_state, sum=compensation_sum
                    )
                )
                consumption_statistics.append(
                    StatisticData(
                        start=start, state=consumption_state, sum=consumption_sum
                    )
                )
                return_statistics.append(
                    StatisticData(start=start, state=return_state, sum=return_sum)
                )

            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(cost_statistics),
                cost_statistic_id,
            )
            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(compensation_statistics),
                compensation_statistic_id,
            )
            async_add_external_statistics(
                self.hass, compensation_metadata, compensation_statistics
            )
            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(consumption_statistics),
                consumption_statistic_id,
            )
            async_add_external_statistics(
                self.hass, consumption_metadata, consumption_statistics
            )
            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(return_statistics),
                return_statistic_id,
            )
            async_add_external_statistics(self.hass, return_metadata, return_statistics)

    async def _async_maybe_migrate_statistics(
        self,
        utility_account_id: str,
        migration_map: dict[str, str],
        metadata_map: dict[str, StatisticMetaData],
    ) -> None:
        """Perform one-time statistics migration based on the provided map.

        Splits negative values from source IDs into target IDs.

        Args:
            utility_account_id: The account ID (for issue_id).
            migration_map: Map from source statistic ID to target statistic ID
                           (e.g., {cost_id: compensation_id}).
            metadata_map: Map of all statistic IDs (source and target) to their metadata.

        """
        if not migration_map:
            return

        need_migration_source_ids = set()
        for source_id, target_id in migration_map.items():
            last_target_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics,
                self.hass,
                1,
                target_id,
                True,
                set(),
            )
            if not last_target_stat:
                need_migration_source_ids.add(source_id)
        if not need_migration_source_ids:
            return

        _LOGGER.info("Starting one-time migration for: %s", need_migration_source_ids)

        processed_stats: dict[str, list[StatisticData]] = {}

        existing_stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            dt_util.utc_from_timestamp(0),
            None,
            need_migration_source_ids,
            "hour",
            None,
            {"start", "state", "sum"},
        )
        for source_id, source_stats in existing_stats.items():
            _LOGGER.debug("Found %d statistics for %s", len(source_stats), source_id)
            if not source_stats:
                continue
            target_id = migration_map[source_id]

            updated_source_stats: list[StatisticData] = []
            new_target_stats: list[StatisticData] = []
            updated_source_sum = 0.0
            new_target_sum = 0.0
            need_migration = False

            prev_sum = 0.0
            for stat in source_stats:
                start = dt_util.utc_from_timestamp(stat["start"])
                curr_sum = cast(float, stat["sum"])
                state = curr_sum - prev_sum
                prev_sum = curr_sum
                if state < 0:
                    need_migration = True

                updated_source_state = max(0, state)
                new_target_state = max(0, -state)

                updated_source_sum += updated_source_state
                new_target_sum += new_target_state

                updated_source_stats.append(
                    StatisticData(
                        start=start, state=updated_source_state, sum=updated_source_sum
                    )
                )
                new_target_stats.append(
                    StatisticData(
                        start=start, state=new_target_state, sum=new_target_sum
                    )
                )

            if need_migration:
                processed_stats[source_id] = updated_source_stats
                processed_stats[target_id] = new_target_stats
            else:
                need_migration_source_ids.remove(source_id)

        if not need_migration_source_ids:
            _LOGGER.debug("No migration needed")
            return

        for stat_id, stats in processed_stats.items():
            _LOGGER.debug("Applying %d migrated stats for %s", len(stats), stat_id)
            async_add_external_statistics(self.hass, metadata_map[stat_id], stats)

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id=f"return_to_grid_migration_{utility_account_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="return_to_grid_migration",
            translation_placeholders={
                "utility_account_id": utility_account_id,
                "energy_settings": "/config/energy",
                "target_ids": "\n".join(
                    {
                        v
                        for k, v in migration_map.items()
                        if k in need_migration_source_ids
                    }
                ),
            },
        )

        # Wait for the migration to finish before continuing
        # to avoid appending new values to the old statistics.
        await get_instance(self.hass).async_block_till_done()

    async def _async_get_cost_reads(
        self, account: Account, time_zone_str: str, start_time: float | None = None
    ) -> list[CostRead]:
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

        tz = await dt_util.async_get_time_zone(time_zone_str)
        if start_time is None:
            start = None
        else:
            start = datetime.fromtimestamp(start_time, tz=tz) - timedelta(days=30)
        end = dt_util.now(tz)
        _LOGGER.debug("Getting monthly cost reads: %s - %s", start, end)
        try:
            cost_reads = await self.api.async_get_cost_reads(
                account, AggregateType.BILL, start, end
            )
        except ApiException as err:
            _LOGGER.error("Error getting monthly cost reads: %s", err)
            raise
        _LOGGER.debug("Got %s monthly cost reads", len(cost_reads))
        if account.read_resolution == ReadResolution.BILLING:
            return cost_reads

        if start_time is None:
            start = end - timedelta(days=3 * 365)
        else:
            if cost_reads:
                start = cost_reads[0].start_time
            assert start
            start = max(start, end - timedelta(days=3 * 365))
        _LOGGER.debug("Getting daily cost reads: %s - %s", start, end)
        try:
            daily_cost_reads = await self.api.async_get_cost_reads(
                account, AggregateType.DAY, start, end
            )
        except ApiException as err:
            _LOGGER.error("Error getting daily cost reads: %s", err)
            raise
        _LOGGER.debug("Got %s daily cost reads", len(daily_cost_reads))
        _update_with_finer_cost_reads(cost_reads, daily_cost_reads)
        if account.read_resolution == ReadResolution.DAY:
            return cost_reads

        if start_time is None:
            start = end - timedelta(days=2 * 30)
        else:
            assert start
            start = max(start, end - timedelta(days=2 * 30))
        _LOGGER.debug("Getting hourly cost reads: %s - %s", start, end)
        try:
            hourly_cost_reads = await self.api.async_get_cost_reads(
                account, AggregateType.HOUR, start, end
            )
        except ApiException as err:
            _LOGGER.error("Error getting hourly cost reads: %s", err)
            raise
        _LOGGER.debug("Got %s hourly cost reads", len(hourly_cost_reads))
        _update_with_finer_cost_reads(cost_reads, hourly_cost_reads)
        _LOGGER.debug("Got %s cost reads", len(cost_reads))
        return cost_reads
