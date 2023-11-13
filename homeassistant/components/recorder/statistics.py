"""Statistics helper."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
import contextlib
import dataclasses
from datetime import datetime, timedelta
from functools import lru_cache, partial
from itertools import chain, groupby
import logging
from operator import itemgetter
import re
from statistics import mean
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

from sqlalchemy import Select, and_, bindparam, func, lambda_stmt, select, text
from sqlalchemy.engine.row import Row
from sqlalchemy.exc import SQLAlchemyError, StatementError
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.lambdas import StatementLambdaElement
import voluptuous as vol

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, callback, valid_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    DataRateConverter,
    DistanceConverter,
    ElectricCurrentConverter,
    ElectricPotentialConverter,
    EnergyConverter,
    InformationConverter,
    MassConverter,
    PowerConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    UnitlessRatioConverter,
    VolumeConverter,
)

from .const import (
    DOMAIN,
    EVENT_RECORDER_5MIN_STATISTICS_GENERATED,
    EVENT_RECORDER_HOURLY_STATISTICS_GENERATED,
    INTEGRATION_PLATFORM_COMPILE_STATISTICS,
    INTEGRATION_PLATFORM_LIST_STATISTIC_IDS,
    INTEGRATION_PLATFORM_VALIDATE_STATISTICS,
    SupportedDialect,
)
from .db_schema import (
    STATISTICS_TABLES,
    Statistics,
    StatisticsBase,
    StatisticsRuns,
    StatisticsShortTerm,
)
from .models import (
    StatisticData,
    StatisticDataTimestamp,
    StatisticMetaData,
    StatisticResult,
    datetime_to_timestamp_or_none,
    process_timestamp,
)
from .util import (
    execute,
    execute_stmt_lambda_element,
    get_instance,
    retryable_database_job,
    session_scope,
)

if TYPE_CHECKING:
    from . import Recorder

QUERY_STATISTICS = (
    Statistics.metadata_id,
    Statistics.start_ts,
    Statistics.mean,
    Statistics.min,
    Statistics.max,
    Statistics.last_reset_ts,
    Statistics.state,
    Statistics.sum,
)

QUERY_STATISTICS_SHORT_TERM = (
    StatisticsShortTerm.metadata_id,
    StatisticsShortTerm.start_ts,
    StatisticsShortTerm.mean,
    StatisticsShortTerm.min,
    StatisticsShortTerm.max,
    StatisticsShortTerm.last_reset_ts,
    StatisticsShortTerm.state,
    StatisticsShortTerm.sum,
)

QUERY_STATISTICS_SUMMARY_MEAN = (
    StatisticsShortTerm.metadata_id,
    func.avg(StatisticsShortTerm.mean),
    func.min(StatisticsShortTerm.min),
    func.max(StatisticsShortTerm.max),
)

QUERY_STATISTICS_SUMMARY_SUM = (
    StatisticsShortTerm.metadata_id,
    StatisticsShortTerm.start_ts,
    StatisticsShortTerm.last_reset_ts,
    StatisticsShortTerm.state,
    StatisticsShortTerm.sum,
    func.row_number()
    .over(  # type: ignore[no-untyped-call]
        partition_by=StatisticsShortTerm.metadata_id,
        order_by=StatisticsShortTerm.start_ts.desc(),
    )
    .label("rownum"),
)


STATISTIC_UNIT_TO_UNIT_CONVERTER: dict[str | None, type[BaseUnitConverter]] = {
    **{unit: DataRateConverter for unit in DataRateConverter.VALID_UNITS},
    **{unit: DistanceConverter for unit in DistanceConverter.VALID_UNITS},
    **{unit: ElectricCurrentConverter for unit in ElectricCurrentConverter.VALID_UNITS},
    **{
        unit: ElectricPotentialConverter
        for unit in ElectricPotentialConverter.VALID_UNITS
    },
    **{unit: EnergyConverter for unit in EnergyConverter.VALID_UNITS},
    **{unit: InformationConverter for unit in InformationConverter.VALID_UNITS},
    **{unit: MassConverter for unit in MassConverter.VALID_UNITS},
    **{unit: PowerConverter for unit in PowerConverter.VALID_UNITS},
    **{unit: PressureConverter for unit in PressureConverter.VALID_UNITS},
    **{unit: SpeedConverter for unit in SpeedConverter.VALID_UNITS},
    **{unit: TemperatureConverter for unit in TemperatureConverter.VALID_UNITS},
    **{unit: UnitlessRatioConverter for unit in UnitlessRatioConverter.VALID_UNITS},
    **{unit: VolumeConverter for unit in VolumeConverter.VALID_UNITS},
}

DATA_SHORT_TERM_STATISTICS_RUN_CACHE = "recorder_short_term_statistics_run_cache"


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class ShortTermStatisticsRunCache:
    """Cache for short term statistics runs."""

    # This is a mapping of metadata_id:id of the last short term
    # statistics run for each metadata_id
    _latest_id_by_metadata_id: dict[int, int] = dataclasses.field(default_factory=dict)

    def get_latest_ids(self, metadata_ids: set[int]) -> dict[int, int]:
        """Return the latest short term statistics ids for the metadata_ids."""
        return {
            metadata_id: id_
            for metadata_id, id_ in self._latest_id_by_metadata_id.items()
            if metadata_id in metadata_ids
        }

    def set_latest_id_for_metadata_id(self, metadata_id: int, id_: int) -> None:
        """Cache the latest id for the metadata_id."""
        self._latest_id_by_metadata_id[metadata_id] = id_

    def set_latest_ids_for_metadata_ids(
        self, metadata_id_to_id: dict[int, int]
    ) -> None:
        """Cache the latest id for the each metadata_id."""
        self._latest_id_by_metadata_id.update(metadata_id_to_id)


class BaseStatisticsRow(TypedDict, total=False):
    """A processed row of statistic data."""

    start: float


class StatisticsRow(BaseStatisticsRow, total=False):
    """A processed row of statistic data."""

    end: float
    last_reset: float | None
    state: float | None
    sum: float | None
    min: float | None
    max: float | None
    mean: float | None
    change: float | None


def _get_unit_class(unit: str | None) -> str | None:
    """Get corresponding unit class from from the statistics unit."""
    if converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(unit):
        return converter.UNIT_CLASS
    return None


def get_display_unit(
    hass: HomeAssistant,
    statistic_id: str,
    statistic_unit: str | None,
) -> str | None:
    """Return the unit which the statistic will be displayed in."""

    if (converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(statistic_unit)) is None:
        return statistic_unit

    state_unit: str | None = statistic_unit
    if state := hass.states.get(statistic_id):
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    if state_unit == statistic_unit or state_unit not in converter.VALID_UNITS:
        # Guard against invalid state unit in the DB
        return statistic_unit

    return state_unit


def _get_statistic_to_display_unit_converter(
    statistic_unit: str | None,
    state_unit: str | None,
    requested_units: dict[str, str] | None,
) -> Callable[[float | None], float | None] | None:
    """Prepare a converter from the statistics unit to display unit."""
    if (converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(statistic_unit)) is None:
        return None

    display_unit: str | None
    unit_class = converter.UNIT_CLASS
    if requested_units and unit_class in requested_units:
        display_unit = requested_units[unit_class]
    else:
        display_unit = state_unit

    if display_unit not in converter.VALID_UNITS:
        # Guard against invalid state unit in the DB
        return None

    if display_unit == statistic_unit:
        return None

    return converter.converter_factory_allow_none(
        from_unit=statistic_unit, to_unit=display_unit
    )


def _get_display_to_statistic_unit_converter(
    display_unit: str | None,
    statistic_unit: str | None,
) -> Callable[[float], float] | None:
    """Prepare a converter from the display unit to the statistics unit."""
    if (
        display_unit == statistic_unit
        or (converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(statistic_unit)) is None
    ):
        return None
    return converter.converter_factory(from_unit=display_unit, to_unit=statistic_unit)


def _get_unit_converter(
    from_unit: str, to_unit: str
) -> Callable[[float | None], float | None] | None:
    """Prepare a converter from a unit to another unit."""
    for conv in STATISTIC_UNIT_TO_UNIT_CONVERTER.values():
        if from_unit in conv.VALID_UNITS and to_unit in conv.VALID_UNITS:
            if from_unit == to_unit:
                return None
            return conv.converter_factory_allow_none(
                from_unit=from_unit, to_unit=to_unit
            )
    raise HomeAssistantError


def can_convert_units(from_unit: str | None, to_unit: str | None) -> bool:
    """Return True if it's possible to convert from from_unit to to_unit."""
    for converter in STATISTIC_UNIT_TO_UNIT_CONVERTER.values():
        if from_unit in converter.VALID_UNITS and to_unit in converter.VALID_UNITS:
            return True
    return False


@dataclasses.dataclass
class PlatformCompiledStatistics:
    """Compiled Statistics from a platform."""

    platform_stats: list[StatisticResult]
    current_metadata: dict[str, tuple[int, StatisticMetaData]]


def split_statistic_id(entity_id: str) -> list[str]:
    """Split a state entity ID into domain and object ID."""
    return entity_id.split(":", 1)


VALID_STATISTIC_ID = re.compile(r"^(?!.+__)(?!_)[\da-z_]+(?<!_):(?!_)[\da-z_]+(?<!_)$")


def valid_statistic_id(statistic_id: str) -> bool:
    """Test if a statistic ID is a valid format.

    Format: <domain>:<statistic> where both are slugs.
    """
    return VALID_STATISTIC_ID.match(statistic_id) is not None


def validate_statistic_id(value: str) -> str:
    """Validate statistic ID."""
    if valid_statistic_id(value):
        return value

    raise vol.Invalid(f"Statistics ID {value} is an invalid statistic ID")


@dataclasses.dataclass
class ValidationIssue:
    """Error or warning message."""

    type: str
    data: dict[str, str | None] | None = None

    def as_dict(self) -> dict:
        """Return dictionary version."""
        return dataclasses.asdict(self)


def get_start_time() -> datetime:
    """Return start time."""
    now = dt_util.utcnow()
    current_period_minutes = now.minute - now.minute % 5
    current_period = now.replace(minute=current_period_minutes, second=0, microsecond=0)
    last_period = current_period - timedelta(minutes=5)
    return last_period


def _compile_hourly_statistics_summary_mean_stmt(
    start_time_ts: float, end_time_ts: float
) -> StatementLambdaElement:
    """Generate the summary mean statement for hourly statistics."""
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS_SUMMARY_MEAN)
        .filter(StatisticsShortTerm.start_ts >= start_time_ts)
        .filter(StatisticsShortTerm.start_ts < end_time_ts)
        .group_by(StatisticsShortTerm.metadata_id)
        .order_by(StatisticsShortTerm.metadata_id)
    )


def _compile_hourly_statistics_last_sum_stmt(
    start_time_ts: float, end_time_ts: float
) -> StatementLambdaElement:
    """Generate the summary mean statement for hourly statistics."""
    return lambda_stmt(
        lambda: select(
            subquery := (
                select(*QUERY_STATISTICS_SUMMARY_SUM)
                .filter(StatisticsShortTerm.start_ts >= start_time_ts)
                .filter(StatisticsShortTerm.start_ts < end_time_ts)
                .subquery()
            )
        )
        .filter(subquery.c.rownum == 1)
        .order_by(subquery.c.metadata_id)
    )


def _compile_hourly_statistics(session: Session, start: datetime) -> None:
    """Compile hourly statistics.

    This will summarize 5-minute statistics for one hour:
    - average, min max is computed by a database query
    - sum is taken from the last 5-minute entry during the hour
    """
    start_time = start.replace(minute=0)
    start_time_ts = start_time.timestamp()
    end_time = start_time + timedelta(hours=1)
    end_time_ts = end_time.timestamp()

    # Compute last hour's average, min, max
    summary: dict[int, StatisticDataTimestamp] = {}
    stmt = _compile_hourly_statistics_summary_mean_stmt(start_time_ts, end_time_ts)
    stats = execute_stmt_lambda_element(session, stmt)

    if stats:
        for stat in stats:
            metadata_id, _mean, _min, _max = stat
            summary[metadata_id] = {
                "start_ts": start_time_ts,
                "mean": _mean,
                "min": _min,
                "max": _max,
            }

    stmt = _compile_hourly_statistics_last_sum_stmt(start_time_ts, end_time_ts)
    # Get last hour's last sum
    stats = execute_stmt_lambda_element(session, stmt)

    if stats:
        for stat in stats:
            metadata_id, start, last_reset_ts, state, _sum, _ = stat
            if metadata_id in summary:
                summary[metadata_id].update(
                    {
                        "last_reset_ts": last_reset_ts,
                        "state": state,
                        "sum": _sum,
                    }
                )
            else:
                summary[metadata_id] = {
                    "start_ts": start_time_ts,
                    "last_reset_ts": last_reset_ts,
                    "state": state,
                    "sum": _sum,
                }

    # Insert compiled hourly statistics in the database
    session.add_all(
        Statistics.from_stats_ts(metadata_id, summary_item)
        for metadata_id, summary_item in summary.items()
    )


@retryable_database_job("compile missing statistics")
def compile_missing_statistics(instance: Recorder) -> bool:
    """Compile missing statistics."""
    now = dt_util.utcnow()
    period_size = 5
    last_period_minutes = now.minute - now.minute % period_size
    last_period = now.replace(minute=last_period_minutes, second=0, microsecond=0)
    start = now - timedelta(days=instance.keep_days)
    start = start.replace(minute=0, second=0, microsecond=0)
    # Commit every 12 hours of data
    commit_interval = 60 / period_size * 12

    with session_scope(
        session=instance.get_session(),
        exception_filter=_filter_unique_constraint_integrity_error(instance),
    ) as session:
        # Find the newest statistics run, if any
        if last_run := session.query(func.max(StatisticsRuns.start)).scalar():
            start = max(start, process_timestamp(last_run) + timedelta(minutes=5))

        periods_without_commit = 0
        while start < last_period:
            periods_without_commit += 1
            end = start + timedelta(minutes=period_size)
            _LOGGER.debug("Compiling missing statistics for %s-%s", start, end)
            modified_statistic_ids = _compile_statistics(
                instance, session, start, end >= last_period
            )
            if periods_without_commit == commit_interval or modified_statistic_ids:
                session.commit()
                session.expunge_all()
                periods_without_commit = 0
            start = end

    return True


@retryable_database_job("compile statistics")
def compile_statistics(instance: Recorder, start: datetime, fire_events: bool) -> bool:
    """Compile 5-minute statistics for all integrations with a recorder platform.

    The actual calculation is delegated to the platforms.
    """
    # Return if we already have 5-minute statistics for the requested period
    with session_scope(
        session=instance.get_session(),
        exception_filter=_filter_unique_constraint_integrity_error(instance),
    ) as session:
        modified_statistic_ids = _compile_statistics(
            instance, session, start, fire_events
        )

    if modified_statistic_ids:
        # In the rare case that we have modified statistic_ids, we reload the modified
        # statistics meta data into the cache in a fresh session to ensure that the
        # cache is up to date and future calls to get statistics meta data will
        # not have to hit the database again.
        with session_scope(session=instance.get_session(), read_only=True) as session:
            instance.statistics_meta_manager.get_many(session, modified_statistic_ids)

    return True


def _get_first_id_stmt(start: datetime) -> StatementLambdaElement:
    """Return a statement that returns the first run_id at start."""
    return lambda_stmt(lambda: select(StatisticsRuns.run_id).filter_by(start=start))


def _compile_statistics(
    instance: Recorder, session: Session, start: datetime, fire_events: bool
) -> set[str]:
    """Compile 5-minute statistics for all integrations with a recorder platform.

    This is a helper function for compile_statistics and compile_missing_statistics
    that does not retry on database errors since both callers already retry.

    returns a set of modified statistic_ids if any were modified.
    """
    assert start.tzinfo == dt_util.UTC, "start must be in UTC"
    end = start + timedelta(minutes=5)
    statistics_meta_manager = instance.statistics_meta_manager
    modified_statistic_ids: set[str] = set()

    # Return if we already have 5-minute statistics for the requested period
    if execute_stmt_lambda_element(session, _get_first_id_stmt(start)):
        _LOGGER.debug("Statistics already compiled for %s-%s", start, end)
        return modified_statistic_ids

    _LOGGER.debug("Compiling statistics for %s-%s", start, end)
    platform_stats: list[StatisticResult] = []
    current_metadata: dict[str, tuple[int, StatisticMetaData]] = {}
    # Collect statistics from all platforms implementing support
    for domain, platform in instance.hass.data[DOMAIN].recorder_platforms.items():
        if not (
            platform_compile_statistics := getattr(
                platform, INTEGRATION_PLATFORM_COMPILE_STATISTICS, None
            )
        ):
            continue
        compiled: PlatformCompiledStatistics = platform_compile_statistics(
            instance.hass, session, start, end
        )
        _LOGGER.debug(
            "Statistics for %s during %s-%s: %s",
            domain,
            start,
            end,
            compiled.platform_stats,
        )
        platform_stats.extend(compiled.platform_stats)
        current_metadata.update(compiled.current_metadata)

    new_short_term_stats: list[StatisticsBase] = []
    updated_metadata_ids: set[int] = set()
    # Insert collected statistics in the database
    for stats in platform_stats:
        modified_statistic_id, metadata_id = statistics_meta_manager.update_or_add(
            session, stats["meta"], current_metadata
        )
        if modified_statistic_id is not None:
            modified_statistic_ids.add(modified_statistic_id)
        updated_metadata_ids.add(metadata_id)
        if new_stat := _insert_statistics(
            session,
            StatisticsShortTerm,
            metadata_id,
            stats["stat"],
        ):
            new_short_term_stats.append(new_stat)

    if start.minute == 55:
        # A full hour is ready, summarize it
        _compile_hourly_statistics(session, start)

    session.add(StatisticsRuns(start=start))

    if fire_events:
        instance.hass.bus.fire(EVENT_RECORDER_5MIN_STATISTICS_GENERATED)
        if start.minute == 55:
            instance.hass.bus.fire(EVENT_RECORDER_HOURLY_STATISTICS_GENERATED)

    if updated_metadata_ids:
        # These are always the newest statistics, so we can update
        # the run cache without having to check the start_ts.
        session.flush()  # populate the ids of the new StatisticsShortTerm rows
        run_cache = get_short_term_statistics_run_cache(instance.hass)
        # metadata_id is typed to allow None, but we know it's not None here
        # so we can safely cast it to int.
        run_cache.set_latest_ids_for_metadata_ids(
            cast(
                dict[int, int],
                {
                    new_stat.metadata_id: new_stat.id
                    for new_stat in new_short_term_stats
                },
            )
        )

    return modified_statistic_ids


def _adjust_sum_statistics(
    session: Session,
    table: type[StatisticsBase],
    metadata_id: int,
    start_time: datetime,
    adj: float,
) -> None:
    """Adjust statistics in the database."""
    start_time_ts = start_time.timestamp()
    try:
        session.query(table).filter_by(metadata_id=metadata_id).filter(
            table.start_ts >= start_time_ts
        ).update(
            {
                table.sum: table.sum + adj,
            },
            synchronize_session=False,
        )
    except SQLAlchemyError:
        _LOGGER.exception(
            "Unexpected exception when updating statistics %s",
            id,
        )


def _insert_statistics(
    session: Session,
    table: type[StatisticsBase],
    metadata_id: int,
    statistic: StatisticData,
) -> StatisticsBase | None:
    """Insert statistics in the database."""
    try:
        stat = table.from_stats(metadata_id, statistic)
        session.add(stat)
        return stat
    except SQLAlchemyError:
        _LOGGER.exception(
            "Unexpected exception when inserting statistics %s:%s ",
            metadata_id,
            statistic,
        )
        return None


def _update_statistics(
    session: Session,
    table: type[StatisticsBase],
    stat_id: int,
    statistic: StatisticData,
) -> None:
    """Insert statistics in the database."""
    try:
        session.query(table).filter_by(id=stat_id).update(
            {
                table.mean: statistic.get("mean"),
                table.min: statistic.get("min"),
                table.max: statistic.get("max"),
                table.last_reset_ts: datetime_to_timestamp_or_none(
                    statistic.get("last_reset")
                ),
                table.state: statistic.get("state"),
                table.sum: statistic.get("sum"),
            },
            synchronize_session=False,
        )
    except SQLAlchemyError:
        _LOGGER.exception(
            "Unexpected exception when updating statistics %s:%s ",
            stat_id,
            statistic,
        )


def get_metadata_with_session(
    instance: Recorder,
    session: Session,
    *,
    statistic_ids: set[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
    statistic_source: str | None = None,
) -> dict[str, tuple[int, StatisticMetaData]]:
    """Fetch meta data.

    Returns a dict of (metadata_id, StatisticMetaData) tuples indexed by statistic_id.
    If statistic_ids is given, fetch metadata only for the listed statistics_ids.
    If statistic_type is given, fetch metadata only for statistic_ids supporting it.
    """
    return instance.statistics_meta_manager.get_many(
        session,
        statistic_ids=statistic_ids,
        statistic_type=statistic_type,
        statistic_source=statistic_source,
    )


def get_metadata(
    hass: HomeAssistant,
    *,
    statistic_ids: set[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
    statistic_source: str | None = None,
) -> dict[str, tuple[int, StatisticMetaData]]:
    """Return metadata for statistic_ids."""
    with session_scope(hass=hass, read_only=True) as session:
        return get_metadata_with_session(
            get_instance(hass),
            session,
            statistic_ids=statistic_ids,
            statistic_type=statistic_type,
            statistic_source=statistic_source,
        )


def clear_statistics(instance: Recorder, statistic_ids: list[str]) -> None:
    """Clear statistics for a list of statistic_ids."""
    with session_scope(session=instance.get_session()) as session:
        instance.statistics_meta_manager.delete(session, statistic_ids)


def update_statistics_metadata(
    instance: Recorder,
    statistic_id: str,
    new_statistic_id: str | None | UndefinedType,
    new_unit_of_measurement: str | None | UndefinedType,
) -> None:
    """Update statistics metadata for a statistic_id."""
    statistics_meta_manager = instance.statistics_meta_manager
    if new_unit_of_measurement is not UNDEFINED:
        with session_scope(session=instance.get_session()) as session:
            statistics_meta_manager.update_unit_of_measurement(
                session, statistic_id, new_unit_of_measurement
            )
    if new_statistic_id is not UNDEFINED and new_statistic_id is not None:
        with session_scope(
            session=instance.get_session(),
            exception_filter=_filter_unique_constraint_integrity_error(instance),
        ) as session:
            statistics_meta_manager.update_statistic_id(
                session, DOMAIN, statistic_id, new_statistic_id
            )


async def async_list_statistic_ids(
    hass: HomeAssistant,
    statistic_ids: set[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
) -> list[dict]:
    """Return all statistic_ids (or filtered one) and unit of measurement.

    Queries the database for existing statistic_ids, as well as integrations with
    a recorder platform for statistic_ids which will be added in the next statistics
    period.
    """
    instance = get_instance(hass)

    if statistic_ids is not None:
        # Try to get the results from the cache since there is nearly
        # always a cache hit.
        statistics_meta_manager = instance.statistics_meta_manager
        metadata = statistics_meta_manager.get_from_cache_threadsafe(statistic_ids)
        if not statistic_ids.difference(metadata):
            result = _statistic_by_id_from_metadata(hass, metadata)
            return _flatten_list_statistic_ids_metadata_result(result)

    return await instance.async_add_executor_job(
        list_statistic_ids,
        hass,
        statistic_ids,
        statistic_type,
    )


def _statistic_by_id_from_metadata(
    hass: HomeAssistant,
    metadata: dict[str, tuple[int, StatisticMetaData]],
) -> dict[str, dict[str, Any]]:
    """Return a list of results for a given metadata dict."""
    return {
        meta["statistic_id"]: {
            "display_unit_of_measurement": get_display_unit(
                hass, meta["statistic_id"], meta["unit_of_measurement"]
            ),
            "has_mean": meta["has_mean"],
            "has_sum": meta["has_sum"],
            "name": meta["name"],
            "source": meta["source"],
            "unit_class": _get_unit_class(meta["unit_of_measurement"]),
            "unit_of_measurement": meta["unit_of_measurement"],
        }
        for _, meta in metadata.values()
    }


def _flatten_list_statistic_ids_metadata_result(
    result: dict[str, dict[str, Any]]
) -> list[dict]:
    """Return a flat dict of metadata."""
    return [
        {
            "statistic_id": _id,
            "display_unit_of_measurement": info["display_unit_of_measurement"],
            "has_mean": info["has_mean"],
            "has_sum": info["has_sum"],
            "name": info.get("name"),
            "source": info["source"],
            "statistics_unit_of_measurement": info["unit_of_measurement"],
            "unit_class": info["unit_class"],
        }
        for _id, info in result.items()
    ]


def list_statistic_ids(
    hass: HomeAssistant,
    statistic_ids: set[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
) -> list[dict]:
    """Return all statistic_ids (or filtered one) and unit of measurement.

    Queries the database for existing statistic_ids, as well as integrations with
    a recorder platform for statistic_ids which will be added in the next statistics
    period.
    """
    result = {}
    instance = get_instance(hass)
    statistics_meta_manager = instance.statistics_meta_manager

    # Query the database
    with session_scope(hass=hass, read_only=True) as session:
        metadata = statistics_meta_manager.get_many(
            session, statistic_type=statistic_type, statistic_ids=statistic_ids
        )
        result = _statistic_by_id_from_metadata(hass, metadata)

    if not statistic_ids or statistic_ids.difference(result):
        # If we want all statistic_ids, or some are missing, we need to query
        # the integrations for the missing ones.
        #
        # Query all integrations with a registered recorder platform
        for platform in hass.data[DOMAIN].recorder_platforms.values():
            if not (
                platform_list_statistic_ids := getattr(
                    platform, INTEGRATION_PLATFORM_LIST_STATISTIC_IDS, None
                )
            ):
                continue
            platform_statistic_ids = platform_list_statistic_ids(
                hass, statistic_ids=statistic_ids, statistic_type=statistic_type
            )

            for key, meta in platform_statistic_ids.items():
                if key in result:
                    # The database has a higher priority than the integration
                    continue
                result[key] = {
                    "display_unit_of_measurement": meta["unit_of_measurement"],
                    "has_mean": meta["has_mean"],
                    "has_sum": meta["has_sum"],
                    "name": meta["name"],
                    "source": meta["source"],
                    "unit_class": _get_unit_class(meta["unit_of_measurement"]),
                    "unit_of_measurement": meta["unit_of_measurement"],
                }

    # Return a list of statistic_id + metadata
    return _flatten_list_statistic_ids_metadata_result(result)


def _reduce_statistics(
    stats: dict[str, list[StatisticsRow]],
    same_period: Callable[[float, float], bool],
    period_start_end: Callable[[float], tuple[float, float]],
    period: timedelta,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Reduce hourly statistics to daily or monthly statistics."""
    result: dict[str, list[StatisticsRow]] = defaultdict(list)
    period_seconds = period.total_seconds()
    _want_mean = "mean" in types
    _want_min = "min" in types
    _want_max = "max" in types
    _want_last_reset = "last_reset" in types
    _want_state = "state" in types
    _want_sum = "sum" in types
    for statistic_id, stat_list in stats.items():
        max_values: list[float] = []
        mean_values: list[float] = []
        min_values: list[float] = []
        prev_stat: StatisticsRow = stat_list[0]
        fake_entry: StatisticsRow = {"start": stat_list[-1]["start"] + period_seconds}

        # Loop over the hourly statistics + a fake entry to end the period
        for statistic in chain(stat_list, (fake_entry,)):
            if not same_period(prev_stat["start"], statistic["start"]):
                start, end = period_start_end(prev_stat["start"])
                # The previous statistic was the last entry of the period
                row: StatisticsRow = {
                    "start": start,
                    "end": end,
                }
                if _want_mean:
                    row["mean"] = mean(mean_values) if mean_values else None
                    mean_values.clear()
                if _want_min:
                    row["min"] = min(min_values) if min_values else None
                    min_values.clear()
                if _want_max:
                    row["max"] = max(max_values) if max_values else None
                    max_values.clear()
                if _want_last_reset:
                    row["last_reset"] = prev_stat.get("last_reset")
                if _want_state:
                    row["state"] = prev_stat.get("state")
                if _want_sum:
                    row["sum"] = prev_stat["sum"]
                result[statistic_id].append(row)
            if _want_max and (_max := statistic.get("max")) is not None:
                max_values.append(_max)
            if _want_mean and (_mean := statistic.get("mean")) is not None:
                mean_values.append(_mean)
            if _want_min and (_min := statistic.get("min")) is not None:
                min_values.append(_min)
            prev_stat = statistic

    return result


def reduce_day_ts_factory() -> (
    tuple[
        Callable[[float, float], bool],
        Callable[[float], tuple[float, float]],
    ]
):
    """Return functions to match same day and day start end."""
    _boundries: tuple[float, float] = (0, 0)

    # We have to recreate _local_from_timestamp in the closure in case the timezone changes
    _local_from_timestamp = partial(
        datetime.fromtimestamp, tz=dt_util.DEFAULT_TIME_ZONE
    )

    def _same_day_ts(time1: float, time2: float) -> bool:
        """Return True if time1 and time2 are in the same date."""
        nonlocal _boundries
        if not _boundries[0] <= time1 < _boundries[1]:
            _boundries = _day_start_end_ts_cached(time1)
        return _boundries[0] <= time2 < _boundries[1]

    def _day_start_end_ts(time: float) -> tuple[float, float]:
        """Return the start and end of the period (day) time is within."""
        start_local = _local_from_timestamp(time).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (
            start_local.astimezone(dt_util.UTC).timestamp(),
            (start_local + timedelta(days=1)).astimezone(dt_util.UTC).timestamp(),
        )

    # We create _day_start_end_ts_cached in the closure in case the timezone changes
    _day_start_end_ts_cached = lru_cache(maxsize=6)(_day_start_end_ts)

    return _same_day_ts, _day_start_end_ts_cached


def _reduce_statistics_per_day(
    stats: dict[str, list[StatisticsRow]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Reduce hourly statistics to daily statistics."""
    _same_day_ts, _day_start_end_ts = reduce_day_ts_factory()
    return _reduce_statistics(
        stats, _same_day_ts, _day_start_end_ts, timedelta(days=1), types
    )


def reduce_week_ts_factory() -> (
    tuple[
        Callable[[float, float], bool],
        Callable[[float], tuple[float, float]],
    ]
):
    """Return functions to match same week and week start end."""
    _boundries: tuple[float, float] = (0, 0)

    # We have to recreate _local_from_timestamp in the closure in case the timezone changes
    _local_from_timestamp = partial(
        datetime.fromtimestamp, tz=dt_util.DEFAULT_TIME_ZONE
    )

    def _same_week_ts(time1: float, time2: float) -> bool:
        """Return True if time1 and time2 are in the same year and week."""
        nonlocal _boundries
        if not _boundries[0] <= time1 < _boundries[1]:
            _boundries = _week_start_end_ts_cached(time1)
        return _boundries[0] <= time2 < _boundries[1]

    def _week_start_end_ts(time: float) -> tuple[float, float]:
        """Return the start and end of the period (week) time is within."""
        nonlocal _boundries
        time_local = _local_from_timestamp(time)
        start_local = time_local.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=time_local.weekday())
        return (
            start_local.astimezone(dt_util.UTC).timestamp(),
            (start_local + timedelta(days=7)).astimezone(dt_util.UTC).timestamp(),
        )

    # We create _week_start_end_ts_cached in the closure in case the timezone changes
    _week_start_end_ts_cached = lru_cache(maxsize=6)(_week_start_end_ts)

    return _same_week_ts, _week_start_end_ts_cached


def _reduce_statistics_per_week(
    stats: dict[str, list[StatisticsRow]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Reduce hourly statistics to weekly statistics."""
    _same_week_ts, _week_start_end_ts = reduce_week_ts_factory()
    return _reduce_statistics(
        stats, _same_week_ts, _week_start_end_ts, timedelta(days=7), types
    )


def _find_month_end_time(timestamp: datetime) -> datetime:
    """Return the end of the month (midnight at the first day of the next month)."""
    # We add 4 days to the end to make sure we are in the next month
    return (timestamp.replace(day=28) + timedelta(days=4)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


def reduce_month_ts_factory() -> (
    tuple[
        Callable[[float, float], bool],
        Callable[[float], tuple[float, float]],
    ]
):
    """Return functions to match same month and month start end."""
    _boundries: tuple[float, float] = (0, 0)

    # We have to recreate _local_from_timestamp in the closure in case the timezone changes
    _local_from_timestamp = partial(
        datetime.fromtimestamp, tz=dt_util.DEFAULT_TIME_ZONE
    )

    def _same_month_ts(time1: float, time2: float) -> bool:
        """Return True if time1 and time2 are in the same year and month."""
        nonlocal _boundries
        if not _boundries[0] <= time1 < _boundries[1]:
            _boundries = _month_start_end_ts_cached(time1)
        return _boundries[0] <= time2 < _boundries[1]

    def _month_start_end_ts(time: float) -> tuple[float, float]:
        """Return the start and end of the period (month) time is within."""
        start_local = _local_from_timestamp(time).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end_local = _find_month_end_time(start_local)
        return (
            start_local.astimezone(dt_util.UTC).timestamp(),
            end_local.astimezone(dt_util.UTC).timestamp(),
        )

    # We create _month_start_end_ts_cached in the closure in case the timezone changes
    _month_start_end_ts_cached = lru_cache(maxsize=6)(_month_start_end_ts)

    return _same_month_ts, _month_start_end_ts_cached


def _reduce_statistics_per_month(
    stats: dict[str, list[StatisticsRow]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Reduce hourly statistics to monthly statistics."""
    _same_month_ts, _month_start_end_ts = reduce_month_ts_factory()
    return _reduce_statistics(
        stats, _same_month_ts, _month_start_end_ts, timedelta(days=31), types
    )


def _generate_statistics_during_period_stmt(
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
    table: type[StatisticsBase],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> StatementLambdaElement:
    """Prepare a database query for statistics during a given period.

    This prepares a lambda_stmt query, so we don't insert the parameters yet.
    """
    start_time_ts = start_time.timestamp()
    stmt = _generate_select_columns_for_types_stmt(table, types)
    stmt += lambda q: q.filter(table.start_ts >= start_time_ts)
    if end_time is not None:
        end_time_ts = end_time.timestamp()
        stmt += lambda q: q.filter(table.start_ts < end_time_ts)
    if metadata_ids:
        stmt += lambda q: q.filter(table.metadata_id.in_(metadata_ids))
    stmt += lambda q: q.order_by(table.metadata_id, table.start_ts)
    return stmt


def _generate_max_mean_min_statistic_in_sub_period_stmt(
    columns: Select,
    start_time: datetime | None,
    end_time: datetime | None,
    table: type[StatisticsBase],
    metadata_id: int,
) -> StatementLambdaElement:
    stmt = lambda_stmt(lambda: columns.filter(table.metadata_id == metadata_id))
    if start_time is not None:
        start_time_ts = start_time.timestamp()
        stmt += lambda q: q.filter(table.start_ts >= start_time_ts)
    if end_time is not None:
        end_time_ts = end_time.timestamp()
        stmt += lambda q: q.filter(table.start_ts < end_time_ts)
    return stmt


def _get_max_mean_min_statistic_in_sub_period(
    session: Session,
    result: dict[str, float],
    start_time: datetime | None,
    end_time: datetime | None,
    table: type[StatisticsBase],
    types: set[Literal["max", "mean", "min", "change"]],
    metadata_id: int,
) -> None:
    """Return max, mean and min during the period."""
    # Calculate max, mean, min
    columns = select()
    if "max" in types:
        columns = columns.add_columns(func.max(table.max))
    if "mean" in types:
        columns = columns.add_columns(func.avg(table.mean))
        columns = columns.add_columns(func.count(table.mean))
    if "min" in types:
        columns = columns.add_columns(func.min(table.min))
    stmt = _generate_max_mean_min_statistic_in_sub_period_stmt(
        columns, start_time, end_time, table, metadata_id
    )
    stats = cast(Sequence[Row[Any]], execute_stmt_lambda_element(session, stmt))
    if not stats:
        return
    if "max" in types and (new_max := stats[0].max) is not None:
        old_max = result.get("max")
        result["max"] = max(new_max, old_max) if old_max is not None else new_max
    if "mean" in types and stats[0].avg is not None:
        # https://github.com/sqlalchemy/sqlalchemy/issues/9127
        duration = stats[0].count * table.duration.total_seconds()  # type: ignore[operator]
        result["duration"] = result.get("duration", 0.0) + duration
        result["mean_acc"] = result.get("mean_acc", 0.0) + stats[0].avg * duration
    if "min" in types and (new_min := stats[0].min) is not None:
        old_min = result.get("min")
        result["min"] = min(new_min, old_min) if old_min is not None else new_min


def _get_max_mean_min_statistic(
    session: Session,
    head_start_time: datetime | None,
    head_end_time: datetime | None,
    main_start_time: datetime | None,
    main_end_time: datetime | None,
    tail_start_time: datetime | None,
    tail_end_time: datetime | None,
    tail_only: bool,
    metadata_id: int,
    types: set[Literal["max", "mean", "min", "change"]],
) -> dict[str, float | None]:
    """Return max, mean and min during the period.

    The mean is a time weighted average, combining hourly and 5-minute statistics if
    necessary.
    """
    max_mean_min: dict[str, float] = {}
    result: dict[str, float | None] = {}

    if tail_start_time is not None:
        # Calculate max, mean, min
        _get_max_mean_min_statistic_in_sub_period(
            session,
            max_mean_min,
            tail_start_time,
            tail_end_time,
            StatisticsShortTerm,
            types,
            metadata_id,
        )

    if not tail_only:
        _get_max_mean_min_statistic_in_sub_period(
            session,
            max_mean_min,
            main_start_time,
            main_end_time,
            Statistics,
            types,
            metadata_id,
        )

    if head_start_time is not None:
        _get_max_mean_min_statistic_in_sub_period(
            session,
            max_mean_min,
            head_start_time,
            head_end_time,
            StatisticsShortTerm,
            types,
            metadata_id,
        )

    if "max" in types:
        result["max"] = max_mean_min.get("max")
    if "mean" in types:
        if "mean_acc" not in max_mean_min:
            result["mean"] = None
        else:
            result["mean"] = max_mean_min["mean_acc"] / max_mean_min["duration"]
    if "min" in types:
        result["min"] = max_mean_min.get("min")
    return result


def _first_statistic(
    session: Session,
    table: type[StatisticsBase],
    metadata_id: int,
) -> datetime | None:
    """Return the data of the oldest statistic row for a given metadata id."""
    stmt = lambda_stmt(
        lambda: select(table.start_ts)
        .filter(table.metadata_id == metadata_id)
        .order_by(table.start_ts.asc())
        .limit(1)
    )
    if stats := cast(Sequence[Row], execute_stmt_lambda_element(session, stmt)):
        return dt_util.utc_from_timestamp(stats[0].start_ts)
    return None


def _get_oldest_sum_statistic(
    session: Session,
    head_start_time: datetime | None,
    main_start_time: datetime | None,
    tail_start_time: datetime | None,
    oldest_stat: datetime | None,
    tail_only: bool,
    metadata_id: int,
) -> float | None:
    """Return the oldest non-NULL sum during the period."""

    def _get_oldest_sum_statistic_in_sub_period(
        session: Session,
        start_time: datetime | None,
        table: type[StatisticsBase],
        metadata_id: int,
    ) -> float | None:
        """Return the oldest non-NULL sum during the period."""
        stmt = lambda_stmt(
            lambda: select(table.sum)
            .filter(table.metadata_id == metadata_id)
            .filter(table.sum.is_not(None))
            .order_by(table.start_ts.asc())
            .limit(1)
        )
        if start_time is not None:
            start_time = start_time + table.duration - timedelta.resolution
            if table == StatisticsShortTerm:
                minutes = start_time.minute - start_time.minute % 5
                period = start_time.replace(minute=minutes, second=0, microsecond=0)
            else:
                period = start_time.replace(minute=0, second=0, microsecond=0)
            prev_period = period - table.duration
            prev_period_ts = prev_period.timestamp()
            stmt += lambda q: q.filter(table.start_ts >= prev_period_ts)
        stats = cast(Sequence[Row], execute_stmt_lambda_element(session, stmt))
        return stats[0].sum if stats else None

    oldest_sum: float | None = None

    # This function won't be called if tail_only is False and main_start_time is None
    # the extra checks are added to satisfy MyPy
    if not tail_only and main_start_time is not None and oldest_stat is not None:
        period = main_start_time.replace(minute=0, second=0, microsecond=0)
        prev_period = period - Statistics.duration
        if prev_period < oldest_stat:
            return 0

    if (
        head_start_time is not None
        and (
            oldest_sum := _get_oldest_sum_statistic_in_sub_period(
                session, head_start_time, StatisticsShortTerm, metadata_id
            )
        )
        is not None
    ):
        return oldest_sum

    if not tail_only:
        if (
            oldest_sum := _get_oldest_sum_statistic_in_sub_period(
                session, main_start_time, Statistics, metadata_id
            )
        ) is not None:
            return oldest_sum
        return 0

    if (
        tail_start_time is not None
        and (
            oldest_sum := _get_oldest_sum_statistic_in_sub_period(
                session, tail_start_time, StatisticsShortTerm, metadata_id
            )
        )
    ) is not None:
        return oldest_sum

    return 0


def _get_newest_sum_statistic(
    session: Session,
    head_start_time: datetime | None,
    head_end_time: datetime | None,
    main_start_time: datetime | None,
    main_end_time: datetime | None,
    tail_start_time: datetime | None,
    tail_end_time: datetime | None,
    tail_only: bool,
    metadata_id: int,
) -> float | None:
    """Return the newest non-NULL sum during the period."""

    def _get_newest_sum_statistic_in_sub_period(
        session: Session,
        start_time: datetime | None,
        end_time: datetime | None,
        table: type[StatisticsBase],
        metadata_id: int,
    ) -> float | None:
        """Return the newest non-NULL sum during the period."""
        stmt = lambda_stmt(
            lambda: select(
                table.sum,
            )
            .filter(table.metadata_id == metadata_id)
            .filter(table.sum.is_not(None))
            .order_by(table.start_ts.desc())
            .limit(1)
        )
        if start_time is not None:
            start_time_ts = start_time.timestamp()
            stmt += lambda q: q.filter(table.start_ts >= start_time_ts)
        if end_time is not None:
            end_time_ts = end_time.timestamp()
            stmt += lambda q: q.filter(table.start_ts < end_time_ts)
        stats = cast(Sequence[Row], execute_stmt_lambda_element(session, stmt))

        return stats[0].sum if stats else None

    newest_sum: float | None = None

    if tail_start_time is not None:
        newest_sum = _get_newest_sum_statistic_in_sub_period(
            session, tail_start_time, tail_end_time, StatisticsShortTerm, metadata_id
        )
        if newest_sum is not None:
            return newest_sum

    if not tail_only:
        newest_sum = _get_newest_sum_statistic_in_sub_period(
            session, main_start_time, main_end_time, Statistics, metadata_id
        )
        if newest_sum is not None:
            return newest_sum

    if head_start_time is not None:
        newest_sum = _get_newest_sum_statistic_in_sub_period(
            session, head_start_time, head_end_time, StatisticsShortTerm, metadata_id
        )

    return newest_sum


def statistic_during_period(
    hass: HomeAssistant,
    start_time: datetime | None,
    end_time: datetime | None,
    statistic_id: str,
    types: set[Literal["max", "mean", "min", "change"]] | None,
    units: dict[str, str] | None,
) -> dict[str, Any]:
    """Return a statistic data point for the UTC period start_time - end_time."""
    metadata = None

    if not types:
        types = {"max", "mean", "min", "change"}

    result: dict[str, Any] = {}

    with session_scope(hass=hass, read_only=True) as session:
        # Fetch metadata for the given statistic_id
        if not (
            metadata := get_instance(hass).statistics_meta_manager.get(
                session, statistic_id
            )
        ):
            return result

        metadata_id = metadata[0]

        oldest_stat = _first_statistic(session, Statistics, metadata_id)
        oldest_5_min_stat = None
        if not valid_statistic_id(statistic_id):
            oldest_5_min_stat = _first_statistic(
                session, StatisticsShortTerm, metadata_id
            )

        # To calculate the summary, data from the statistics (hourly) and
        # short_term_statistics (5 minute) tables is combined
        # - The short term statistics table is used for the head and tail of the period,
        #   if the period it doesn't start or end on a full hour
        # - The statistics table is used for the remainder of the time
        now = dt_util.utcnow()
        if end_time is not None and end_time > now:
            end_time = now

        tail_only = (
            start_time is not None
            and end_time is not None
            and end_time - start_time < timedelta(hours=1)
        )

        # Calculate the head period
        head_start_time: datetime | None = None
        head_end_time: datetime | None = None
        if (
            not tail_only
            and oldest_stat is not None
            and oldest_5_min_stat is not None
            and oldest_5_min_stat - oldest_stat < timedelta(hours=1)
            and (start_time is None or start_time < oldest_5_min_stat)
        ):
            # To improve accuracy of averaged for statistics which were added within
            # recorder's retention period.
            head_start_time = oldest_5_min_stat
            head_end_time = oldest_5_min_stat.replace(
                minute=0, second=0, microsecond=0
            ) + timedelta(hours=1)
        elif not tail_only and start_time is not None and start_time.minute:
            head_start_time = start_time
            head_end_time = start_time.replace(
                minute=0, second=0, microsecond=0
            ) + timedelta(hours=1)

        # Calculate the tail period
        tail_start_time: datetime | None = None
        tail_end_time: datetime | None = None
        if end_time is None:
            tail_start_time = now.replace(minute=0, second=0, microsecond=0)
        elif end_time.minute:
            tail_start_time = (
                start_time
                if tail_only
                else end_time.replace(minute=0, second=0, microsecond=0)
            )
            tail_end_time = end_time

        # Calculate the main period
        main_start_time: datetime | None = None
        main_end_time: datetime | None = None
        if not tail_only:
            main_start_time = start_time if head_end_time is None else head_end_time
            main_end_time = end_time if tail_start_time is None else tail_start_time

        if not types.isdisjoint({"max", "mean", "min"}):
            result = _get_max_mean_min_statistic(
                session,
                head_start_time,
                head_end_time,
                main_start_time,
                main_end_time,
                tail_start_time,
                tail_end_time,
                tail_only,
                metadata_id,
                types,
            )

        if "change" in types:
            oldest_sum: float | None
            if start_time is None:
                oldest_sum = 0.0
            else:
                oldest_sum = _get_oldest_sum_statistic(
                    session,
                    head_start_time,
                    main_start_time,
                    tail_start_time,
                    oldest_stat,
                    tail_only,
                    metadata_id,
                )
            newest_sum = _get_newest_sum_statistic(
                session,
                head_start_time,
                head_end_time,
                main_start_time,
                main_end_time,
                tail_start_time,
                tail_end_time,
                tail_only,
                metadata_id,
            )
            # Calculate the difference between the oldest and newest sum
            if oldest_sum is not None and newest_sum is not None:
                result["change"] = newest_sum - oldest_sum
            else:
                result["change"] = None

    state_unit = unit = metadata[1]["unit_of_measurement"]
    if state := hass.states.get(statistic_id):
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    convert = _get_statistic_to_display_unit_converter(unit, state_unit, units)

    if not convert:
        return result
    return {key: convert(value) for key, value in result.items()}


_type_column_mapping = {
    "last_reset": "last_reset_ts",
    "max": "max",
    "mean": "mean",
    "min": "min",
    "state": "state",
    "sum": "sum",
}


def _generate_select_columns_for_types_stmt(
    table: type[StatisticsBase],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> StatementLambdaElement:
    columns = select(table.metadata_id, table.start_ts)
    track_on: list[str | None] = [
        table.__tablename__,  # type: ignore[attr-defined]
    ]
    for key, column in _type_column_mapping.items():
        if key in types:
            columns = columns.add_columns(getattr(table, column))
            track_on.append(column)
        else:
            track_on.append(None)
    return lambda_stmt(lambda: columns, track_on=track_on)


def _extract_metadata_and_discard_impossible_columns(
    metadata: dict[str, tuple[int, StatisticMetaData]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> list[int]:
    """Extract metadata ids from metadata and discard impossible columns."""
    metadata_ids = []
    has_mean = False
    has_sum = False
    for metadata_id, stats_metadata in metadata.values():
        metadata_ids.append(metadata_id)
        has_mean |= stats_metadata["has_mean"]
        has_sum |= stats_metadata["has_sum"]
    if not has_mean:
        types.discard("mean")
        types.discard("min")
        types.discard("max")
    if not has_sum:
        types.discard("sum")
        types.discard("state")
    return metadata_ids


def _augment_result_with_change(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    units: dict[str, str] | None,
    _types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
    table: type[Statistics | StatisticsShortTerm],
    metadata: dict[str, tuple[int, StatisticMetaData]],
    result: dict[str, list[StatisticsRow]],
) -> None:
    """Add change to the result."""
    drop_sum = "sum" not in _types
    prev_sums = {}
    if tmp := _statistics_at_time(
        session,
        {metadata[statistic_id][0] for statistic_id in result},
        table,
        start_time,
        {"sum"},
    ):
        _metadata = dict(metadata.values())
        for row in tmp:
            metadata_by_id = _metadata[row.metadata_id]
            statistic_id = metadata_by_id["statistic_id"]

            state_unit = unit = metadata_by_id["unit_of_measurement"]
            if state := hass.states.get(statistic_id):
                state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            convert = _get_statistic_to_display_unit_converter(unit, state_unit, units)

            if convert is not None:
                prev_sums[statistic_id] = convert(row.sum)
            else:
                prev_sums[statistic_id] = row.sum

    for statistic_id, rows in result.items():
        prev_sum = prev_sums.get(statistic_id) or 0
        for statistics_row in rows:
            if "sum" not in statistics_row:
                continue
            if drop_sum:
                _sum = statistics_row.pop("sum")
            else:
                _sum = statistics_row["sum"]
            if _sum is None:
                statistics_row["change"] = None
                continue
            statistics_row["change"] = _sum - prev_sum
            prev_sum = _sum


def _statistics_during_period_with_session(
    hass: HomeAssistant,
    session: Session,
    start_time: datetime,
    end_time: datetime | None,
    statistic_ids: set[str] | None,
    period: Literal["5minute", "day", "hour", "week", "month"],
    units: dict[str, str] | None,
    _types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Return statistic data points during UTC period start_time - end_time.

    If end_time is omitted, returns statistics newer than or equal to start_time.
    If statistic_ids is omitted, returns statistics for all statistics ids.
    """
    if statistic_ids is not None and not isinstance(statistic_ids, set):
        # This is for backwards compatibility to avoid a breaking change
        # for custom integrations that call this method.
        statistic_ids = set(statistic_ids)  # type: ignore[unreachable]
    # Fetch metadata for the given (or all) statistic_ids
    metadata = get_instance(hass).statistics_meta_manager.get_many(
        session, statistic_ids=statistic_ids
    )
    if not metadata:
        return {}

    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]] = set()
    for stat_type in _types:
        if stat_type == "change":
            types.add("sum")
            continue
        types.add(stat_type)

    metadata_ids = None
    if statistic_ids is not None:
        metadata_ids = _extract_metadata_and_discard_impossible_columns(metadata, types)

    # Align start_time and end_time with the period
    if period == "day":
        start_time = dt_util.as_local(start_time).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_time = start_time.replace()
        if end_time is not None:
            end_local = dt_util.as_local(end_time)
            end_time = end_local.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
    elif period == "week":
        start_local = dt_util.as_local(start_time)
        start_time = start_local.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=start_local.weekday())
        if end_time is not None:
            end_local = dt_util.as_local(end_time)
            end_time = (
                end_local.replace(hour=0, minute=0, second=0, microsecond=0)
                - timedelta(days=end_local.weekday())
                + timedelta(days=7)
            )
    elif period == "month":
        start_time = dt_util.as_local(start_time).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if end_time is not None:
            end_time = _find_month_end_time(dt_util.as_local(end_time))

    table: type[Statistics | StatisticsShortTerm] = (
        Statistics if period != "5minute" else StatisticsShortTerm
    )
    stmt = _generate_statistics_during_period_stmt(
        start_time, end_time, metadata_ids, table, types
    )
    stats = cast(
        Sequence[Row], execute_stmt_lambda_element(session, stmt, orm_rows=False)
    )

    if not stats:
        return {}

    result = _sorted_statistics_to_dict(
        hass,
        session,
        stats,
        statistic_ids,
        metadata,
        True,
        table,
        start_time,
        units,
        types,
    )

    if period == "day":
        result = _reduce_statistics_per_day(result, types)

    if period == "week":
        result = _reduce_statistics_per_week(result, types)

    if period == "month":
        result = _reduce_statistics_per_month(result, types)

    if "change" in _types:
        _augment_result_with_change(
            hass, session, start_time, units, _types, table, metadata, result
        )

    # Return statistics combined with metadata
    return result


def statistics_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None,
    statistic_ids: set[str] | None,
    period: Literal["5minute", "day", "hour", "week", "month"],
    units: dict[str, str] | None,
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Return statistic data points during UTC period start_time - end_time.

    If end_time is omitted, returns statistics newer than or equal to start_time.
    If statistic_ids is omitted, returns statistics for all statistics ids.
    """
    with session_scope(hass=hass, read_only=True) as session:
        return _statistics_during_period_with_session(
            hass,
            session,
            start_time,
            end_time,
            statistic_ids,
            period,
            units,
            types,
        )


def _get_last_statistics_stmt(
    metadata_id: int,
    number_of_stats: int,
) -> StatementLambdaElement:
    """Generate a statement for number_of_stats statistics for a given statistic_id."""
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS)
        .filter_by(metadata_id=metadata_id)
        .order_by(Statistics.metadata_id, Statistics.start_ts.desc())
        .limit(number_of_stats)
    )


def _get_last_statistics_short_term_stmt(
    metadata_id: int,
    number_of_stats: int,
) -> StatementLambdaElement:
    """Generate a statement for number_of_stats short term statistics.

    For a given statistic_id.
    """
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS_SHORT_TERM)
        .filter_by(metadata_id=metadata_id)
        .order_by(StatisticsShortTerm.metadata_id, StatisticsShortTerm.start_ts.desc())
        .limit(number_of_stats)
    )


def _get_last_statistics(
    hass: HomeAssistant,
    number_of_stats: int,
    statistic_id: str,
    convert_units: bool,
    table: type[StatisticsBase],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Return the last number_of_stats statistics for a given statistic_id."""
    statistic_ids = {statistic_id}
    with session_scope(hass=hass, read_only=True) as session:
        # Fetch metadata for the given statistic_id
        metadata = get_instance(hass).statistics_meta_manager.get_many(
            session, statistic_ids=statistic_ids
        )
        if not metadata:
            return {}
        metadata_ids = _extract_metadata_and_discard_impossible_columns(metadata, types)
        metadata_id = metadata_ids[0]
        if table == Statistics:
            stmt = _get_last_statistics_stmt(metadata_id, number_of_stats)
        else:
            stmt = _get_last_statistics_short_term_stmt(metadata_id, number_of_stats)
        stats = cast(
            Sequence[Row], execute_stmt_lambda_element(session, stmt, orm_rows=False)
        )

        if not stats:
            return {}

        # Return statistics combined with metadata
        return _sorted_statistics_to_dict(
            hass,
            session,
            stats,
            statistic_ids,
            metadata,
            convert_units,
            table,
            None,
            None,
            types,
        )


def get_last_statistics(
    hass: HomeAssistant,
    number_of_stats: int,
    statistic_id: str,
    convert_units: bool,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Return the last number_of_stats statistics for a statistic_id."""
    return _get_last_statistics(
        hass, number_of_stats, statistic_id, convert_units, Statistics, types
    )


def get_last_short_term_statistics(
    hass: HomeAssistant,
    number_of_stats: int,
    statistic_id: str,
    convert_units: bool,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Return the last number_of_stats short term statistics for a statistic_id."""
    return _get_last_statistics(
        hass, number_of_stats, statistic_id, convert_units, StatisticsShortTerm, types
    )


def get_latest_short_term_statistics_by_ids(
    session: Session, ids: Iterable[int]
) -> list[Row]:
    """Return the latest short term statistics for a list of ids."""
    stmt = _latest_short_term_statistics_by_ids_stmt(ids)
    return list(
        cast(
            Sequence[Row],
            execute_stmt_lambda_element(session, stmt),
        )
    )


def _latest_short_term_statistics_by_ids_stmt(
    ids: Iterable[int],
) -> StatementLambdaElement:
    """Create the statement for finding the latest short term stat rows by id."""
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS_SHORT_TERM).filter(
            StatisticsShortTerm.id.in_(ids)
        )
    )


def get_latest_short_term_statistics_with_session(
    hass: HomeAssistant,
    session: Session,
    statistic_ids: set[str],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
    metadata: dict[str, tuple[int, StatisticMetaData]] | None = None,
) -> dict[str, list[StatisticsRow]]:
    """Return the latest short term statistics for a list of statistic_ids with a session."""
    # Fetch metadata for the given statistic_ids
    if not metadata:
        metadata = get_instance(hass).statistics_meta_manager.get_many(
            session, statistic_ids=statistic_ids
        )
    if not metadata:
        return {}
    metadata_ids = set(
        _extract_metadata_and_discard_impossible_columns(metadata, types)
    )
    run_cache = get_short_term_statistics_run_cache(hass)
    # Try to find the latest short term statistics ids for the metadata_ids
    # from the run cache first if we have it. If the run cache references
    # a non-existent id because of a purge, we will detect it missing in the
    # next step and run a query to re-populate the cache.
    stats: list[Row] = []
    if metadata_id_to_id := run_cache.get_latest_ids(metadata_ids):
        stats = get_latest_short_term_statistics_by_ids(
            session, metadata_id_to_id.values()
        )
    # If we are missing some metadata_ids in the run cache, we need run a query
    # to populate the cache for each metadata_id, and then run another query
    # to get the latest short term statistics for the missing metadata_ids.
    if (missing_metadata_ids := metadata_ids - set(metadata_id_to_id)) and (
        found_latest_ids := {
            latest_id
            for metadata_id in missing_metadata_ids
            if (
                latest_id := cache_latest_short_term_statistic_id_for_metadata_id(
                    run_cache,
                    session,
                    metadata_id,
                )
            )
            is not None
        }
    ):
        stats.extend(get_latest_short_term_statistics_by_ids(session, found_latest_ids))

    if not stats:
        return {}

    # Return statistics combined with metadata
    return _sorted_statistics_to_dict(
        hass,
        session,
        stats,
        statistic_ids,
        metadata,
        False,
        StatisticsShortTerm,
        None,
        None,
        types,
    )


def _generate_statistics_at_time_stmt(
    table: type[StatisticsBase],
    metadata_ids: set[int],
    start_time_ts: float,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> StatementLambdaElement:
    """Create the statement for finding the statistics for a given time."""
    stmt = _generate_select_columns_for_types_stmt(table, types)
    stmt += lambda q: q.join(
        (
            most_recent_statistic_ids := (
                select(
                    func.max(table.start_ts).label("max_start_ts"),
                    table.metadata_id.label("max_metadata_id"),
                )
                .filter(table.start_ts < start_time_ts)
                .filter(table.metadata_id.in_(metadata_ids))
                .group_by(table.metadata_id)
                .subquery()
            )
        ),
        and_(
            table.start_ts == most_recent_statistic_ids.c.max_start_ts,
            table.metadata_id == most_recent_statistic_ids.c.max_metadata_id,
        ),
    )
    return stmt


def _statistics_at_time(
    session: Session,
    metadata_ids: set[int],
    table: type[StatisticsBase],
    start_time: datetime,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> Sequence[Row] | None:
    """Return last known statistics, earlier than start_time, for the metadata_ids."""
    start_time_ts = start_time.timestamp()
    stmt = _generate_statistics_at_time_stmt(table, metadata_ids, start_time_ts, types)
    return cast(Sequence[Row], execute_stmt_lambda_element(session, stmt))


def _fast_build_sum_list(
    stats_list: list[Row],
    table_duration_seconds: float,
    convert: Callable | None,
    start_ts_idx: int,
    sum_idx: int,
) -> list[StatisticsRow]:
    """Build a list of sum statistics."""
    if convert:
        return [
            {
                "start": (start_ts := db_state[start_ts_idx]),
                "end": start_ts + table_duration_seconds,
                "sum": convert(db_state[sum_idx]),
            }
            for db_state in stats_list
        ]
    return [
        {
            "start": (start_ts := db_state[start_ts_idx]),
            "end": start_ts + table_duration_seconds,
            "sum": db_state[sum_idx],
        }
        for db_state in stats_list
    ]


def _sorted_statistics_to_dict(  # noqa: C901
    hass: HomeAssistant,
    session: Session,
    stats: Sequence[Row[Any]],
    statistic_ids: set[str] | None,
    _metadata: dict[str, tuple[int, StatisticMetaData]],
    convert_units: bool,
    table: type[StatisticsBase],
    start_time: datetime | None,
    units: dict[str, str] | None,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> dict[str, list[StatisticsRow]]:
    """Convert SQL results into JSON friendly data structure."""
    assert stats, "stats must not be empty"  # Guard against implementation error
    result: dict[str, list[StatisticsRow]] = defaultdict(list)
    metadata = dict(_metadata.values())
    # Identify metadata IDs for which no data was available at the requested start time
    field_map: dict[str, int] = {key: idx for idx, key in enumerate(stats[0]._fields)}
    metadata_id_idx = field_map["metadata_id"]
    start_ts_idx = field_map["start_ts"]
    stats_by_meta_id: dict[int, list[Row]] = {}
    seen_statistic_ids: set[str] = set()
    key_func = itemgetter(metadata_id_idx)
    for meta_id, group in groupby(stats, key_func):
        stats_list = stats_by_meta_id[meta_id] = list(group)
        seen_statistic_ids.add(metadata[meta_id]["statistic_id"])

    # Set all statistic IDs to empty lists in result set to maintain the order
    if statistic_ids is not None:
        for stat_id in statistic_ids:
            # Only set the statistic ID if it is in the data to
            # avoid having to do a second loop to remove the
            # statistic IDs that are not in the data at the end
            if stat_id in seen_statistic_ids:
                result[stat_id] = []

    # Figure out which fields we need to extract from the SQL result
    # and which indices they have in the result so we can avoid the overhead
    # of doing a dict lookup for each row
    mean_idx = field_map["mean"] if "mean" in types else None
    min_idx = field_map["min"] if "min" in types else None
    max_idx = field_map["max"] if "max" in types else None
    last_reset_ts_idx = field_map["last_reset_ts"] if "last_reset" in types else None
    state_idx = field_map["state"] if "state" in types else None
    sum_idx = field_map["sum"] if "sum" in types else None
    sum_only = len(types) == 1 and sum_idx is not None
    # Append all statistic entries, and optionally do unit conversion
    table_duration_seconds = table.duration.total_seconds()
    for meta_id, stats_list in stats_by_meta_id.items():
        metadata_by_id = metadata[meta_id]
        statistic_id = metadata_by_id["statistic_id"]
        if convert_units:
            state_unit = unit = metadata_by_id["unit_of_measurement"]
            if state := hass.states.get(statistic_id):
                state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            convert = _get_statistic_to_display_unit_converter(unit, state_unit, units)
        else:
            convert = None

        if sum_only:
            # This function is extremely flexible and can handle all types of
            # statistics, but in practice we only ever use a few combinations.
            #
            # For energy, we only need sum statistics, so we can optimize
            # this path to avoid the overhead of the more generic function.
            assert sum_idx is not None
            result[statistic_id] = _fast_build_sum_list(
                stats_list,
                table_duration_seconds,
                convert,
                start_ts_idx,
                sum_idx,
            )
            continue

        ent_results_append = result[statistic_id].append
        #
        # The below loop is a red hot path for energy, and every
        # optimization counts in here.
        #
        # Specifically, we want to avoid function calls,
        # attribute lookups, and dict lookups as much as possible.
        #
        for db_state in stats_list:
            row: StatisticsRow = {
                "start": (start_ts := db_state[start_ts_idx]),
                "end": start_ts + table_duration_seconds,
            }
            if last_reset_ts_idx is not None:
                row["last_reset"] = db_state[last_reset_ts_idx]
            if convert:
                if mean_idx is not None:
                    row["mean"] = convert(db_state[mean_idx])
                if min_idx is not None:
                    row["min"] = convert(db_state[min_idx])
                if max_idx is not None:
                    row["max"] = convert(db_state[max_idx])
                if state_idx is not None:
                    row["state"] = convert(db_state[state_idx])
                if sum_idx is not None:
                    row["sum"] = convert(db_state[sum_idx])
            else:
                if mean_idx is not None:
                    row["mean"] = db_state[mean_idx]
                if min_idx is not None:
                    row["min"] = db_state[min_idx]
                if max_idx is not None:
                    row["max"] = db_state[max_idx]
                if state_idx is not None:
                    row["state"] = db_state[state_idx]
                if sum_idx is not None:
                    row["sum"] = db_state[sum_idx]
            ent_results_append(row)

    return result


def validate_statistics(hass: HomeAssistant) -> dict[str, list[ValidationIssue]]:
    """Validate statistics."""
    platform_validation: dict[str, list[ValidationIssue]] = {}
    for platform in hass.data[DOMAIN].recorder_platforms.values():
        if platform_validate_statistics := getattr(
            platform, INTEGRATION_PLATFORM_VALIDATE_STATISTICS, None
        ):
            platform_validation.update(platform_validate_statistics(hass))
    return platform_validation


def _statistics_exists(
    session: Session,
    table: type[StatisticsBase],
    metadata_id: int,
    start: datetime,
) -> int | None:
    """Return id if a statistics entry already exists."""
    start_ts = start.timestamp()
    result = (
        session.query(table.id)
        .filter((table.metadata_id == metadata_id) & (table.start_ts == start_ts))
        .first()
    )
    return result.id if result else None


@callback
def _async_import_statistics(
    hass: HomeAssistant,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
) -> None:
    """Validate timestamps and insert an import_statistics job in the queue."""
    for statistic in statistics:
        start = statistic["start"]
        if start.tzinfo is None or start.tzinfo.utcoffset(start) is None:
            raise HomeAssistantError("Naive timestamp")
        if start.minute != 0 or start.second != 0 or start.microsecond != 0:
            raise HomeAssistantError("Invalid timestamp")
        statistic["start"] = dt_util.as_utc(start)

        if "last_reset" in statistic and statistic["last_reset"] is not None:
            last_reset = statistic["last_reset"]
            if (
                last_reset.tzinfo is None
                or last_reset.tzinfo.utcoffset(last_reset) is None
            ):
                raise HomeAssistantError("Naive timestamp")
            statistic["last_reset"] = dt_util.as_utc(last_reset)

    # Insert job in recorder's queue
    get_instance(hass).async_import_statistics(metadata, statistics, Statistics)


@callback
def async_import_statistics(
    hass: HomeAssistant,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
) -> None:
    """Import hourly statistics from an internal source.

    This inserts an import_statistics job in the recorder's queue.
    """
    if not valid_entity_id(metadata["statistic_id"]):
        raise HomeAssistantError("Invalid statistic_id")

    # The source must not be empty and must be aligned with the statistic_id
    if not metadata["source"] or metadata["source"] != DOMAIN:
        raise HomeAssistantError("Invalid source")

    _async_import_statistics(hass, metadata, statistics)


@callback
def async_add_external_statistics(
    hass: HomeAssistant,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
) -> None:
    """Add hourly statistics from an external source.

    This inserts an import_statistics job in the recorder's queue.
    """
    # The statistic_id has same limitations as an entity_id, but with a ':' as separator
    if not valid_statistic_id(metadata["statistic_id"]):
        raise HomeAssistantError("Invalid statistic_id")

    # The source must not be empty and must be aligned with the statistic_id
    domain, _object_id = split_statistic_id(metadata["statistic_id"])
    if not metadata["source"] or metadata["source"] != domain:
        raise HomeAssistantError("Invalid source")

    _async_import_statistics(hass, metadata, statistics)


def _filter_unique_constraint_integrity_error(
    instance: Recorder,
) -> Callable[[Exception], bool]:
    def _filter_unique_constraint_integrity_error(err: Exception) -> bool:
        """Handle unique constraint integrity errors."""
        if not isinstance(err, StatementError):
            return False

        assert instance.engine is not None
        dialect_name = instance.engine.dialect.name

        ignore = False
        if (
            dialect_name == SupportedDialect.SQLITE
            and "UNIQUE constraint failed" in str(err)
        ):
            ignore = True
        if (
            dialect_name == SupportedDialect.POSTGRESQL
            and err.orig
            and hasattr(err.orig, "pgcode")
            and err.orig.pgcode == "23505"
        ):
            ignore = True
        if (
            dialect_name == SupportedDialect.MYSQL
            and err.orig
            and hasattr(err.orig, "args")
        ):
            with contextlib.suppress(TypeError):
                if err.orig.args[0] == 1062:
                    ignore = True

        if ignore:
            _LOGGER.warning(
                (
                    "Blocked attempt to insert duplicated statistic rows, please report"
                    " at %s"
                ),
                "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+recorder%22",
                exc_info=err,
            )

        return ignore

    return _filter_unique_constraint_integrity_error


def _import_statistics_with_session(
    instance: Recorder,
    session: Session,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
    table: type[StatisticsBase],
) -> bool:
    """Import statistics to the database."""
    statistics_meta_manager = instance.statistics_meta_manager
    old_metadata_dict = statistics_meta_manager.get_many(
        session, statistic_ids={metadata["statistic_id"]}
    )
    _, metadata_id = statistics_meta_manager.update_or_add(
        session, metadata, old_metadata_dict
    )
    for stat in statistics:
        if stat_id := _statistics_exists(session, table, metadata_id, stat["start"]):
            _update_statistics(session, table, stat_id, stat)
        else:
            _insert_statistics(session, table, metadata_id, stat)

    if table != StatisticsShortTerm:
        return True

    # We just inserted new short term statistics, so we need to update the
    # ShortTermStatisticsRunCache with the latest id for the metadata_id
    run_cache = get_short_term_statistics_run_cache(instance.hass)
    cache_latest_short_term_statistic_id_for_metadata_id(
        run_cache, session, metadata_id
    )

    return True


@singleton(DATA_SHORT_TERM_STATISTICS_RUN_CACHE)
def get_short_term_statistics_run_cache(
    hass: HomeAssistant,
) -> ShortTermStatisticsRunCache:
    """Get the short term statistics run cache."""
    return ShortTermStatisticsRunCache()


def cache_latest_short_term_statistic_id_for_metadata_id(
    run_cache: ShortTermStatisticsRunCache,
    session: Session,
    metadata_id: int,
) -> int | None:
    """Cache the latest short term statistic for a given metadata_id.

    Returns the id of the latest short term statistic for the metadata_id
    that was added to the cache, or None if no latest short term statistic
    was found for the metadata_id.
    """
    if latest := cast(
        Sequence[Row],
        execute_stmt_lambda_element(
            session, _find_latest_short_term_statistic_for_metadata_id_stmt(metadata_id)
        ),
    ):
        id_: int = latest[0].id
        run_cache.set_latest_id_for_metadata_id(metadata_id, id_)
        return id_
    return None


def _find_latest_short_term_statistic_for_metadata_id_stmt(
    metadata_id: int,
) -> StatementLambdaElement:
    """Create a statement to find the latest short term statistics for a metadata_id."""
    #
    # This code only looks up one row, and should not be refactored to
    # lookup multiple using func.max
    # or similar, as that will cause the query to be significantly slower
    # for DBMs such as PostgreSQL that will have to do a full scan
    #
    # For PostgreSQL a combined query plan looks like:
    # (actual time=2.218..893.909 rows=170531 loops=1)
    #
    # For PostgreSQL a separate query plan looks like:
    # (actual time=0.301..0.301 rows=1 loops=1)
    #
    #
    return lambda_stmt(
        lambda: select(
            StatisticsShortTerm.id,
        )
        .where(StatisticsShortTerm.metadata_id == metadata_id)
        .order_by(StatisticsShortTerm.start_ts.desc())
        .limit(1)
    )


@retryable_database_job("statistics")
def import_statistics(
    instance: Recorder,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
    table: type[StatisticsBase],
) -> bool:
    """Process an import_statistics job."""

    with session_scope(
        session=instance.get_session(),
        exception_filter=_filter_unique_constraint_integrity_error(instance),
    ) as session:
        return _import_statistics_with_session(
            instance, session, metadata, statistics, table
        )


@retryable_database_job("adjust_statistics")
def adjust_statistics(
    instance: Recorder,
    statistic_id: str,
    start_time: datetime,
    sum_adjustment: float,
    adjustment_unit: str,
) -> bool:
    """Process an add_statistics job."""

    with session_scope(session=instance.get_session()) as session:
        metadata = instance.statistics_meta_manager.get_many(
            session, statistic_ids={statistic_id}
        )
        if statistic_id not in metadata:
            return True

        statistic_unit = metadata[statistic_id][1]["unit_of_measurement"]
        if convert := _get_display_to_statistic_unit_converter(
            adjustment_unit, statistic_unit
        ):
            sum_adjustment = convert(sum_adjustment)

        _adjust_sum_statistics(
            session,
            StatisticsShortTerm,
            metadata[statistic_id][0],
            start_time,
            sum_adjustment,
        )

        _adjust_sum_statistics(
            session,
            Statistics,
            metadata[statistic_id][0],
            start_time.replace(minute=0),
            sum_adjustment,
        )

    return True


def _change_statistics_unit_for_table(
    session: Session,
    table: type[StatisticsBase],
    metadata_id: int,
    convert: Callable[[float | None], float | None],
) -> None:
    """Insert statistics in the database."""
    columns = (table.id, table.mean, table.min, table.max, table.state, table.sum)
    query = session.query(*columns).filter_by(metadata_id=bindparam("metadata_id"))
    rows = execute(query.params(metadata_id=metadata_id))
    for row in rows:
        session.query(table).filter(table.id == row.id).update(
            {
                table.mean: convert(row.mean),
                table.min: convert(row.min),
                table.max: convert(row.max),
                table.state: convert(row.state),
                table.sum: convert(row.sum),
            },
            synchronize_session=False,
        )


def change_statistics_unit(
    instance: Recorder,
    statistic_id: str,
    new_unit: str,
    old_unit: str,
) -> None:
    """Change statistics unit for a statistic_id."""
    statistics_meta_manager = instance.statistics_meta_manager
    with session_scope(session=instance.get_session()) as session:
        metadata = statistics_meta_manager.get(session, statistic_id)

        # Guard against the statistics being removed or updated before the
        # change_statistics_unit job executes
        if (
            metadata is None
            or metadata[1]["source"] != DOMAIN
            or metadata[1]["unit_of_measurement"] != old_unit
        ):
            _LOGGER.warning("Could not change statistics unit for %s", statistic_id)
            return

        metadata_id = metadata[0]

        if not (convert := _get_unit_converter(old_unit, new_unit)):
            _LOGGER.warning(
                "Statistics unit of measurement for %s is already %s",
                statistic_id,
                new_unit,
            )
            return

        tables: tuple[type[StatisticsBase], ...] = (
            Statistics,
            StatisticsShortTerm,
        )
        for table in tables:
            _change_statistics_unit_for_table(session, table, metadata_id, convert)

        statistics_meta_manager.update_unit_of_measurement(
            session, statistic_id, new_unit
        )


@callback
def async_change_statistics_unit(
    hass: HomeAssistant,
    statistic_id: str,
    *,
    new_unit_of_measurement: str,
    old_unit_of_measurement: str,
) -> None:
    """Change statistics unit for a statistic_id."""
    if not can_convert_units(old_unit_of_measurement, new_unit_of_measurement):
        raise HomeAssistantError(
            f"Can't convert {old_unit_of_measurement} to {new_unit_of_measurement}"
        )

    get_instance(hass).async_change_statistics_unit(
        statistic_id,
        new_unit_of_measurement=new_unit_of_measurement,
        old_unit_of_measurement=old_unit_of_measurement,
    )


def cleanup_statistics_timestamp_migration(instance: Recorder) -> bool:
    """Clean up the statistics migration from timestamp to datetime.

    Returns False if there are more rows to update.
    Returns True if all rows have been updated.
    """
    engine = instance.engine
    assert engine is not None
    if engine.dialect.name == SupportedDialect.SQLITE:
        for table in STATISTICS_TABLES:
            with session_scope(session=instance.get_session()) as session:
                session.connection().execute(
                    text(
                        f"update {table} set start = NULL, created = NULL, last_reset = NULL;"  # noqa: S608
                    )
                )
    elif engine.dialect.name == SupportedDialect.MYSQL:
        for table in STATISTICS_TABLES:
            with session_scope(session=instance.get_session()) as session:
                if (
                    session.connection()
                    .execute(
                        text(
                            f"UPDATE {table} set start=NULL, created=NULL, last_reset=NULL where start is not NULL LIMIT 100000;"  # noqa: S608
                        )
                    )
                    .rowcount
                ):
                    # We have more rows to update so return False
                    # to indicate we need to run again
                    return False
    elif engine.dialect.name == SupportedDialect.POSTGRESQL:
        for table in STATISTICS_TABLES:
            with session_scope(session=instance.get_session()) as session:
                if (
                    session.connection()
                    .execute(
                        text(
                            f"UPDATE {table} set start=NULL, created=NULL, last_reset=NULL "  # noqa: S608
                            f"where id in (select id from {table} where start is not NULL LIMIT 100000)"
                        )
                    )
                    .rowcount
                ):
                    # We have more rows to update so return False
                    # to indicate we need to run again
                    return False

    from .migration import _drop_index  # pylint: disable=import-outside-toplevel

    for table in STATISTICS_TABLES:
        _drop_index(instance.get_session, table, f"ix_{table}_start")
    # We have no more rows to update so return True
    # to indicate we are done
    return True
