"""Coordinator to handle Opower connections."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any, cast, override

from opower import (
    Account,
    AggregateType,
    CostRead,
    Forecast,
    MeterType,
    Opower,
    ReadComponent,
    ReadResolution,
    create_cookie_jar,
)
from opower.exceptions import ApiException, CannotConnect, InvalidAuth, MfaChallenge

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
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify
from homeassistant.util.unit_conversion import EnergyConverter, VolumeConverter

from .const import CONF_LOGIN_DATA, CONF_TOTP_SECRET, CONF_UTILITY, DOMAIN

_LOGGER = logging.getLogger(__name__)

type OpowerConfigEntry = ConfigEntry[OpowerCoordinator]


@dataclass
class OpowerData:
    """Class to hold Opower data."""

    account: Account
    forecast: Forecast | None
    last_changed: datetime | None
    last_updated: datetime


@dataclass
class _RatePeriodStatistics:
    """Statistics of one rate period (a time-of-use period or a tier)."""

    consumption_metadata: StatisticMetaData
    cost_metadata: StatisticMetaData
    consumption_sum: float = 0.0
    cost_sum: float = 0.0
    # Start of the stored statistic the sums continue from, None if the
    # period has no stored statistics yet.
    last_stats_time: float | None = None
    consumption_statistics: list[StatisticData] = field(default_factory=list)
    cost_statistics: list[StatisticData] = field(default_factory=list)


def _rate_period_key(component: ReadComponent) -> str | None:
    """Return the rate period key of a read component.

    Time-of-use utilities report the period in day_part, e.g. "ON_PEAK+RT02/TOD"
    where the period is the part before the "+". Tiered utilities report the
    tier in tier_number. Returns None if the component has neither.
    """
    if component.day_part:
        key = component.day_part.split("+", 1)[0]
    elif component.tier_number is not None:
        key = f"tier_{component.tier_number}"
    else:
        return None
    return slugify(key) or None


def _rate_periods(
    cost_reads: list[CostRead],
    id_prefix: str,
    name_prefix: str,
    consumption_unit_class: str,
    consumption_unit: str,
) -> dict[str, _RatePeriodStatistics]:
    """Return the rate periods (time-of-use periods or tiers) found in the reads.

    Utilities on time-of-use or tiered rates break each read down into
    components, one per rate period. A consumption and a cost statistic
    is created for every period so the Energy dashboard can show how much
    energy and money went to each one. Utilities without components get
    no additional statistics.
    """
    rate_periods: dict[str, _RatePeriodStatistics] = {}
    for cost_read in cost_reads:
        for component in cost_read.read_components:
            if (key := _rate_period_key(component)) is None or key in rate_periods:
                continue
            label = key.replace("_", " ")
            rate_periods[key] = _RatePeriodStatistics(
                consumption_metadata=StatisticMetaData(
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=f"{name_prefix} {label} consumption",
                    source=DOMAIN,
                    statistic_id=f"{DOMAIN}:{id_prefix}_{key}_energy_consumption",
                    unit_class=consumption_unit_class,
                    unit_of_measurement=consumption_unit,
                ),
                cost_metadata=StatisticMetaData(
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=f"{name_prefix} {label} cost",
                    source=DOMAIN,
                    statistic_id=f"{DOMAIN}:{id_prefix}_{key}_energy_cost",
                    unit_class=None,
                    unit_of_measurement=None,
                ),
            )
    if rate_periods:
        _LOGGER.debug("Found rate periods: %s", list(rate_periods))
    return rate_periods


def _safe_get_sum(records: list[Any]) -> float:
    if records and "sum" in records[0]:
        return float(records[0]["sum"])
    return 0.0


class OpowerCoordinator(DataUpdateCoordinator[dict[str, OpowerData]]):
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
            async_create_clientsession(hass, cookie_jar=create_cookie_jar()),
            config_entry.data[CONF_UTILITY],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data.get(CONF_TOTP_SECRET),
            config_entry.data.get(CONF_LOGIN_DATA),
        )

        @callback
        def _dummy_listener() -> None:
            pass

        # Force the coordinator to periodically update by
        # registering at least one listener.
        # Needed when the _async_update_data below returns {}
        # for utilities that don't provide forecast, which results
        # to no sensors added, no registered listeners, and thus
        # _async_update_data not periodically getting called which
        # is needed for _insert_statistics.
        self.async_add_listener(_dummy_listener)

    @override
    async def _async_update_data(
        self,
    ) -> dict[str, OpowerData]:
        """Fetch data from API endpoint."""
        try:
            # Login expires after a few minutes.
            # Given the infrequent updating (every 12h)
            # assume previous session has expired and re-login.
            await self.api.async_login()
        except (InvalidAuth, MfaChallenge) as err:
            _LOGGER.error("Error during login: %s", err)
            raise ConfigEntryAuthFailed from err
        except CannotConnect as err:
            _LOGGER.error("Error during login: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="login_error",
                translation_placeholders={"error": str(err)},
            ) from err

        try:
            accounts = await self.api.async_get_accounts()
        except ApiException as err:
            _LOGGER.error("Error getting accounts: %s", err)
            raise

        try:
            forecasts_list = await self.api.async_get_forecast()
        except ApiException as err:
            _LOGGER.error("Error getting forecasts: %s", err)
            raise

        forecasts = {f.account.utility_account_id: f for f in forecasts_list}
        _LOGGER.debug("Updating sensor data with: %s", forecasts)

        # Because Opower provides historical usage/cost with a delay of a couple of days
        # we need to insert data into statistics.
        last_changed_per_account = await self._insert_statistics(accounts)
        return {
            account.utility_account_id: OpowerData(
                account=account,
                forecast=forecasts.get(account.utility_account_id),
                last_changed=last_changed_per_account.get(account.utility_account_id),
                last_updated=dt_util.utcnow(),
            )
            for account in accounts
        }

    async def _insert_statistics(self, accounts: list[Account]) -> dict[str, datetime]:
        """Insert Opower statistics."""
        last_changed_per_account: dict[str, datetime] = {}
        for account in accounts:
            id_prefix = (
                (
                    f"{self.api.utility.subdomain()}_{account.meter_type.name}_"
                    f"{account.utility_account_id}"
                )
                # Some utilities like AEP have "-" in their account id.
                # Other utilities like ngny-gas have "-" in their subdomain.
                # Replace it with "_" to avoid "Invalid statistic_id"
                .replace("-", "_")
                .lower()
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
                unit_class=None,
                unit_of_measurement=None,
            )
            compensation_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} compensation",
                source=DOMAIN,
                statistic_id=compensation_statistic_id,
                unit_class=None,
                unit_of_measurement=None,
            )
            consumption_unit_class = (
                EnergyConverter.UNIT_CLASS
                if account.meter_type is MeterType.ELEC
                else VolumeConverter.UNIT_CLASS
            )
            consumption_unit = (
                UnitOfEnergy.KILO_WATT_HOUR
                if account.meter_type is MeterType.ELEC
                else UnitOfVolume.CENTUM_CUBIC_FEET
            )
            consumption_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} consumption",
                source=DOMAIN,
                statistic_id=consumption_statistic_id,
                unit_class=consumption_unit_class,
                unit_of_measurement=consumption_unit,
            )
            return_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} return",
                source=DOMAIN,
                statistic_id=return_statistic_id,
                unit_class=consumption_unit_class,
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
                migrated = await self._async_maybe_migrate_statistics(
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
                if migrated:
                    # Skip update to avoid working on old data since
                    # the migration is done
                    # asynchronously. Update the statistics in the next refresh in 12h.
                    _LOGGER.debug(
                        "Statistics migration completed. Skipping update for now"
                    )
                    continue
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

                cost_sum = _safe_get_sum(stats.get(cost_statistic_id, []))
                compensation_sum = _safe_get_sum(
                    stats.get(compensation_statistic_id, [])
                )
                consumption_sum = _safe_get_sum(stats.get(consumption_statistic_id, []))
                return_sum = _safe_get_sum(stats.get(return_statistic_id, []))
                last_stats_time = stats[consumption_statistic_id][0]["start"]

            if cost_reads:
                last_changed_per_account[account.utility_account_id] = cost_reads[
                    -1
                ].start_time
            elif last_stats_time is not None:
                last_changed_per_account[account.utility_account_id] = (
                    dt_util.utc_from_timestamp(last_stats_time)
                )

            rate_periods = _rate_periods(
                cost_reads,
                id_prefix,
                name_prefix,
                consumption_unit_class,
                consumption_unit,
            )
            if rate_periods and last_stats_time is not None:
                await self._async_init_rate_period_sums(
                    rate_periods, dt_util.utc_from_timestamp(last_stats_time)
                )
            new_rate_periods = [
                key
                for key, rate_period in rate_periods.items()
                if rate_period.last_stats_time is None
            ]

            cost_statistics = []
            compensation_statistics = []
            consumption_statistics = []
            return_statistics = []

            for cost_read in cost_reads:
                start = cost_read.start_time

                # The account totals and each rate period continue from their own
                # stored statistics, so each skips the reads up to its own last
                # stored point. A period that has none yet, e.g. right after
                # upgrading, must not skip the reads the totals already have.
                period_consumption = dict.fromkeys(rate_periods, 0.0)
                period_cost = dict.fromkeys(rate_periods, 0.0)
                for component in cost_read.read_components:
                    if (key := _rate_period_key(component)) is None:
                        continue
                    period_consumption[key] += component.consumption
                    period_cost[key] += component.cost
                for key, rate_period in rate_periods.items():
                    if (
                        rate_period.last_stats_time is not None
                        and start.timestamp() <= rate_period.last_stats_time
                    ):
                        continue
                    consumption_state = max(0, period_consumption[key])
                    cost_state = max(0, period_cost[key])
                    rate_period.consumption_sum += consumption_state
                    rate_period.cost_sum += cost_state
                    rate_period.consumption_statistics.append(
                        StatisticData(
                            start=start,
                            state=consumption_state,
                            sum=rate_period.consumption_sum,
                        )
                    )
                    rate_period.cost_statistics.append(
                        StatisticData(
                            start=start, state=cost_state, sum=rate_period.cost_sum
                        )
                    )

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
            for rate_period in rate_periods.values():
                for metadata, statistics in (
                    (
                        rate_period.consumption_metadata,
                        rate_period.consumption_statistics,
                    ),
                    (rate_period.cost_metadata, rate_period.cost_statistics),
                ):
                    _LOGGER.debug(
                        "Adding %s statistics for %s",
                        len(statistics),
                        metadata["statistic_id"],
                    )
                    async_add_external_statistics(self.hass, metadata, statistics)
            if new_rate_periods:
                self._async_create_rate_period_issue(
                    account.utility_account_id,
                    [rate_periods[key] for key in new_rate_periods],
                )

        return last_changed_per_account

    @callback
    def _async_create_rate_period_issue(
        self, utility_account_id: str, rate_periods: list[_RatePeriodStatistics]
    ) -> None:
        """Tell the user which rate period statistics were created.

        Statistics do not show up anywhere until they are added to the Energy
        dashboard, so this points the user at the new ones and at the
        Energy configuration page.
        """
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id=(
                f"rate_period_statistics_{self.config_entry.entry_id}_"
                f"{utility_account_id}"
            ),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="rate_period_statistics",
            translation_placeholders={
                "utility_account_id": utility_account_id,
                "energy_settings": "/config/energy",
                "statistic_names": "\n".join(
                    f"- {rate_period.consumption_metadata['name']} "
                    f"with {rate_period.cost_metadata['name']}"
                    for rate_period in rate_periods
                ),
            },
        )

    async def _async_init_rate_period_sums(
        self, rate_periods: dict[str, _RatePeriodStatistics], start: datetime
    ) -> None:
        """Continue the rate period sums from the statistics stored at start.

        A period that is missing at start, e.g. a summer-only period seen
        again after winter, continues from its last stored statistic instead.
        A period that has never been stored starts from zero and keeps
        last_stats_time None.
        """
        statistic_ids = {
            statistic_id
            for rate_period in rate_periods.values()
            for statistic_id in (
                rate_period.consumption_metadata["statistic_id"],
                rate_period.cost_metadata["statistic_id"],
            )
        }
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start,
            start + timedelta(seconds=1),
            statistic_ids,
            "hour",
            None,
            {"sum"},
        )
        for statistic_id in statistic_ids - set(stats):
            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
            )
            if last_stat and last_stat[statistic_id][0]["start"] < start.timestamp():
                stats[statistic_id] = last_stat[statistic_id]
        for rate_period in rate_periods.values():
            consumption_stats = stats.get(
                rate_period.consumption_metadata["statistic_id"], []
            )
            if consumption_stats:
                rate_period.last_stats_time = float(consumption_stats[0]["start"])
            rate_period.consumption_sum = _safe_get_sum(consumption_stats)
            rate_period.cost_sum = _safe_get_sum(
                stats.get(rate_period.cost_metadata["statistic_id"], [])
            )

    async def _async_maybe_migrate_statistics(
        self,
        utility_account_id: str,
        migration_map: dict[str, str],
        metadata_map: dict[str, StatisticMetaData],
    ) -> bool:
        """Perform one-time statistics migration based on the provided map.

        Splits negative values from source IDs into target IDs.

        Args:
            utility_account_id: The account ID (for issue_id).
            migration_map: Map from source statistic ID to target statistic ID
                           (e.g., {cost_id: compensation_id}).
            metadata_map: Map of all statistic IDs (source and target)
                         to their metadata.

        """
        if not migration_map:
            return False

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
            return False

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
                need_migration_source_ids.remove(source_id)
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
            return False

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
                        str(metadata_map[v]["name"])
                        for k, v in migration_map.items()
                        if k in need_migration_source_ids
                    }
                ),
            },
        )

        return True

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
        if account.read_resolution is ReadResolution.BILLING:
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
        if account.read_resolution is ReadResolution.DAY:
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
