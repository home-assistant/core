"""Statistics helper."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
import contextlib
import dataclasses
from datetime import datetime, timedelta
from functools import partial
from itertools import chain, groupby
import json
import logging
import os
import re
from statistics import mean
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import bindparam, func, lambda_stmt, select
from sqlalchemy.engine.row import Row
from sqlalchemy.exc import SQLAlchemyError, StatementError
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import literal_column, true
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.sql.selectable import Subquery
import voluptuous as vol

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import Event, HomeAssistant, callback, valid_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    DistanceConverter,
    EnergyConverter,
    MassConverter,
    PowerConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    VolumeConverter,
)

from .const import DOMAIN, MAX_ROWS_TO_PURGE, SupportedDialect
from .db_schema import (
    Statistics,
    StatisticsBase,
    StatisticsMeta,
    StatisticsRuns,
    StatisticsShortTerm,
)
from .models import (
    StatisticData,
    StatisticMetaData,
    StatisticResult,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
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

QUERY_STATISTICS = [
    Statistics.metadata_id,
    Statistics.start,
    Statistics.mean,
    Statistics.min,
    Statistics.max,
    Statistics.last_reset,
    Statistics.state,
    Statistics.sum,
]

QUERY_STATISTICS_SHORT_TERM = [
    StatisticsShortTerm.metadata_id,
    StatisticsShortTerm.start,
    StatisticsShortTerm.mean,
    StatisticsShortTerm.min,
    StatisticsShortTerm.max,
    StatisticsShortTerm.last_reset,
    StatisticsShortTerm.state,
    StatisticsShortTerm.sum,
]

QUERY_STATISTICS_SUMMARY_MEAN = [
    StatisticsShortTerm.metadata_id,
    func.avg(StatisticsShortTerm.mean),
    func.min(StatisticsShortTerm.min),
    func.max(StatisticsShortTerm.max),
]

QUERY_STATISTICS_SUMMARY_SUM = [
    StatisticsShortTerm.metadata_id,
    StatisticsShortTerm.start,
    StatisticsShortTerm.last_reset,
    StatisticsShortTerm.state,
    StatisticsShortTerm.sum,
    func.row_number()
    .over(
        partition_by=StatisticsShortTerm.metadata_id,
        order_by=StatisticsShortTerm.start.desc(),
    )
    .label("rownum"),
]

QUERY_STATISTIC_META = [
    StatisticsMeta.id,
    StatisticsMeta.statistic_id,
    StatisticsMeta.source,
    StatisticsMeta.unit_of_measurement,
    StatisticsMeta.has_mean,
    StatisticsMeta.has_sum,
    StatisticsMeta.name,
]


STATISTIC_UNIT_TO_UNIT_CONVERTER: dict[str | None, type[BaseUnitConverter]] = {
    **{unit: DistanceConverter for unit in DistanceConverter.VALID_UNITS},
    **{unit: EnergyConverter for unit in EnergyConverter.VALID_UNITS},
    **{unit: MassConverter for unit in MassConverter.VALID_UNITS},
    **{unit: PowerConverter for unit in PowerConverter.VALID_UNITS},
    **{unit: PressureConverter for unit in PressureConverter.VALID_UNITS},
    **{unit: SpeedConverter for unit in SpeedConverter.VALID_UNITS},
    **{unit: TemperatureConverter for unit in TemperatureConverter.VALID_UNITS},
    **{unit: VolumeConverter for unit in VolumeConverter.VALID_UNITS},
}


_LOGGER = logging.getLogger(__name__)


def _get_unit_class(unit: str | None) -> str | None:
    """Get corresponding unit class from from the statistics unit."""
    if converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(unit):
        return converter.UNIT_CLASS
    return None


def _get_statistic_to_display_unit_converter(
    statistic_unit: str | None,
    state_unit: str | None,
    requested_units: dict[str, str] | None,
) -> Callable[[float | None], float | None]:
    """Prepare a converter from the statistics unit to display unit."""

    def no_conversion(val: float | None) -> float | None:
        """Return val."""
        return val

    if statistic_unit is None:
        return no_conversion

    if (converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(statistic_unit)) is None:
        return no_conversion

    display_unit: str | None
    unit_class = converter.UNIT_CLASS
    if requested_units and unit_class in requested_units:
        display_unit = requested_units[unit_class]
    else:
        display_unit = state_unit

    if display_unit not in converter.VALID_UNITS:
        # Guard against invalid state unit in the DB
        return no_conversion

    def from_normalized_unit(
        val: float | None, conv: type[BaseUnitConverter], from_unit: str, to_unit: str
    ) -> float | None:
        """Return val."""
        if val is None:
            return val
        return conv.convert(val, from_unit=from_unit, to_unit=to_unit)

    return partial(
        from_normalized_unit,
        conv=converter,
        from_unit=statistic_unit,
        to_unit=display_unit,
    )


def _get_display_to_statistic_unit_converter(
    display_unit: str | None,
    statistic_unit: str | None,
) -> Callable[[float], float]:
    """Prepare a converter from the display unit to the statistics unit."""

    def no_conversion(val: float) -> float:
        """Return val."""
        return val

    if statistic_unit is None:
        return no_conversion

    if (converter := STATISTIC_UNIT_TO_UNIT_CONVERTER.get(statistic_unit)) is None:
        return no_conversion

    return partial(converter.convert, from_unit=display_unit, to_unit=statistic_unit)


def _get_unit_converter(
    from_unit: str, to_unit: str
) -> Callable[[float | None], float | None]:
    """Prepare a converter from a unit to another unit."""

    def convert_units(
        val: float | None, conv: type[BaseUnitConverter], from_unit: str, to_unit: str
    ) -> float | None:
        """Return converted val."""
        if val is None:
            return val
        return conv.convert(val, from_unit=from_unit, to_unit=to_unit)

    for conv in STATISTIC_UNIT_TO_UNIT_CONVERTER.values():
        if from_unit in conv.VALID_UNITS and to_unit in conv.VALID_UNITS:
            return partial(
                convert_units, conv=conv, from_unit=from_unit, to_unit=to_unit
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


def async_setup(hass: HomeAssistant) -> None:
    """Set up the history hooks."""

    @callback
    def _async_entity_id_changed(event: Event) -> None:
        get_instance(hass).async_update_statistics_metadata(
            event.data["old_entity_id"], new_statistic_id=event.data["entity_id"]
        )

    @callback
    def entity_registry_changed_filter(event: Event) -> bool:
        """Handle entity_id changed filter."""
        if event.data["action"] != "update" or "old_entity_id" not in event.data:
            return False

        return True

    @callback
    def setup_entity_registry_event_handler(hass: HomeAssistant) -> None:
        """Subscribe to event registry events."""
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            _async_entity_id_changed,
            event_filter=entity_registry_changed_filter,
        )

    async_at_start(hass, setup_entity_registry_event_handler)


def get_start_time() -> datetime:
    """Return start time."""
    now = dt_util.utcnow()
    current_period_minutes = now.minute - now.minute % 5
    current_period = now.replace(minute=current_period_minutes, second=0, microsecond=0)
    last_period = current_period - timedelta(minutes=5)
    return last_period


def _update_or_add_metadata(
    session: Session,
    new_metadata: StatisticMetaData,
    old_metadata_dict: dict[str, tuple[int, StatisticMetaData]],
) -> int:
    """Get metadata_id for a statistic_id.

    If the statistic_id is previously unknown, add it. If it's already known, update
    metadata if needed.

    Updating metadata source is not possible.
    """
    statistic_id = new_metadata["statistic_id"]
    if statistic_id not in old_metadata_dict:
        meta = StatisticsMeta.from_meta(new_metadata)
        session.add(meta)
        session.flush()  # Flush to get the metadata id assigned
        _LOGGER.debug(
            "Added new statistics metadata for %s, new_metadata: %s",
            statistic_id,
            new_metadata,
        )
        return meta.id  # type: ignore[no-any-return]

    metadata_id, old_metadata = old_metadata_dict[statistic_id]
    if (
        old_metadata["has_mean"] != new_metadata["has_mean"]
        or old_metadata["has_sum"] != new_metadata["has_sum"]
        or old_metadata["name"] != new_metadata["name"]
        or old_metadata["unit_of_measurement"] != new_metadata["unit_of_measurement"]
    ):
        session.query(StatisticsMeta).filter_by(statistic_id=statistic_id).update(
            {
                StatisticsMeta.has_mean: new_metadata["has_mean"],
                StatisticsMeta.has_sum: new_metadata["has_sum"],
                StatisticsMeta.name: new_metadata["name"],
                StatisticsMeta.unit_of_measurement: new_metadata["unit_of_measurement"],
            },
            synchronize_session=False,
        )
        _LOGGER.debug(
            "Updated statistics metadata for %s, old_metadata: %s, new_metadata: %s",
            statistic_id,
            old_metadata,
            new_metadata,
        )

    return metadata_id


def _find_duplicates(
    session: Session, table: type[Statistics | StatisticsShortTerm]
) -> tuple[list[int], list[dict]]:
    """Find duplicated statistics."""
    subquery = (
        session.query(
            table.start,
            table.metadata_id,
            literal_column("1").label("is_duplicate"),
        )
        .group_by(table.metadata_id, table.start)
        .having(func.count() > 1)
        .subquery()
    )
    query = (
        session.query(table)
        .outerjoin(
            subquery,
            (subquery.c.metadata_id == table.metadata_id)
            & (subquery.c.start == table.start),
        )
        .filter(subquery.c.is_duplicate == 1)
        .order_by(table.metadata_id, table.start, table.id.desc())
        .limit(1000 * MAX_ROWS_TO_PURGE)
    )
    duplicates = execute(query)
    original_as_dict = {}
    start = None
    metadata_id = None
    duplicate_ids: list[int] = []
    non_identical_duplicates_as_dict: list[dict] = []

    if not duplicates:
        return (duplicate_ids, non_identical_duplicates_as_dict)

    def columns_to_dict(duplicate: type[Statistics | StatisticsShortTerm]) -> dict:
        """Convert a SQLAlchemy row to dict."""
        dict_ = {}
        for key in duplicate.__mapper__.c.keys():
            dict_[key] = getattr(duplicate, key)
        return dict_

    def compare_statistic_rows(row1: dict, row2: dict) -> bool:
        """Compare two statistics rows, ignoring id and created."""
        ignore_keys = ["id", "created"]
        keys1 = set(row1).difference(ignore_keys)
        keys2 = set(row2).difference(ignore_keys)
        return keys1 == keys2 and all(row1[k] == row2[k] for k in keys1)

    for duplicate in duplicates:
        if start != duplicate.start or metadata_id != duplicate.metadata_id:
            original_as_dict = columns_to_dict(duplicate)
            start = duplicate.start
            metadata_id = duplicate.metadata_id
            continue
        duplicate_as_dict = columns_to_dict(duplicate)
        duplicate_ids.append(duplicate.id)
        if not compare_statistic_rows(original_as_dict, duplicate_as_dict):
            non_identical_duplicates_as_dict.append(
                {"duplicate": duplicate_as_dict, "original": original_as_dict}
            )

    return (duplicate_ids, non_identical_duplicates_as_dict)


def _delete_duplicates_from_table(
    session: Session, table: type[Statistics | StatisticsShortTerm]
) -> tuple[int, list[dict]]:
    """Identify and delete duplicated statistics from a specified table."""
    all_non_identical_duplicates: list[dict] = []
    total_deleted_rows = 0
    while True:
        duplicate_ids, non_identical_duplicates = _find_duplicates(session, table)
        if not duplicate_ids:
            break
        all_non_identical_duplicates.extend(non_identical_duplicates)
        for i in range(0, len(duplicate_ids), MAX_ROWS_TO_PURGE):
            deleted_rows = (
                session.query(table)
                .filter(table.id.in_(duplicate_ids[i : i + MAX_ROWS_TO_PURGE]))
                .delete(synchronize_session=False)
            )
            total_deleted_rows += deleted_rows
    return (total_deleted_rows, all_non_identical_duplicates)


def delete_statistics_duplicates(hass: HomeAssistant, session: Session) -> None:
    """Identify and delete duplicated statistics.

    A backup will be made of duplicated statistics before it is deleted.
    """
    deleted_statistics_rows, non_identical_duplicates = _delete_duplicates_from_table(
        session, Statistics
    )
    if deleted_statistics_rows:
        _LOGGER.info("Deleted %s duplicated statistics rows", deleted_statistics_rows)

    if non_identical_duplicates:
        isotime = dt_util.utcnow().isoformat()
        backup_file_name = f"deleted_statistics.{isotime}.json"
        backup_path = hass.config.path(STORAGE_DIR, backup_file_name)

        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, "w", encoding="utf8") as backup_file:
            json.dump(
                non_identical_duplicates,
                backup_file,
                indent=4,
                sort_keys=True,
                cls=JSONEncoder,
            )
        _LOGGER.warning(
            "Deleted %s non identical duplicated %s rows, a backup of the deleted rows "
            "has been saved to %s",
            len(non_identical_duplicates),
            Statistics.__tablename__,
            backup_path,
        )

    deleted_short_term_statistics_rows, _ = _delete_duplicates_from_table(
        session, StatisticsShortTerm
    )
    if deleted_short_term_statistics_rows:
        _LOGGER.warning(
            "Deleted duplicated short term statistic rows, please report at %s",
            "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+recorder%22",
        )


def _find_statistics_meta_duplicates(session: Session) -> list[int]:
    """Find duplicated statistics_meta."""
    # When querying the database, be careful to only explicitly query for columns
    # which were present in schema version 29. If querying the table, SQLAlchemy
    # will refer to future columns.
    subquery = (
        session.query(
            StatisticsMeta.statistic_id,
            literal_column("1").label("is_duplicate"),
        )
        .group_by(StatisticsMeta.statistic_id)
        .having(func.count() > 1)
        .subquery()
    )
    query = (
        session.query(StatisticsMeta.statistic_id, StatisticsMeta.id)
        .outerjoin(
            subquery,
            (subquery.c.statistic_id == StatisticsMeta.statistic_id),
        )
        .filter(subquery.c.is_duplicate == 1)
        .order_by(StatisticsMeta.statistic_id, StatisticsMeta.id.desc())
        .limit(1000 * MAX_ROWS_TO_PURGE)
    )
    duplicates = execute(query)
    statistic_id = None
    duplicate_ids: list[int] = []

    if not duplicates:
        return duplicate_ids

    for duplicate in duplicates:
        if statistic_id != duplicate.statistic_id:
            statistic_id = duplicate.statistic_id
            continue
        duplicate_ids.append(duplicate.id)

    return duplicate_ids


def _delete_statistics_meta_duplicates(session: Session) -> int:
    """Identify and delete duplicated statistics from a specified table."""
    total_deleted_rows = 0
    while True:
        duplicate_ids = _find_statistics_meta_duplicates(session)
        if not duplicate_ids:
            break
        for i in range(0, len(duplicate_ids), MAX_ROWS_TO_PURGE):
            deleted_rows = (
                session.query(StatisticsMeta)
                .filter(StatisticsMeta.id.in_(duplicate_ids[i : i + MAX_ROWS_TO_PURGE]))
                .delete(synchronize_session=False)
            )
            total_deleted_rows += deleted_rows
    return total_deleted_rows


def delete_statistics_meta_duplicates(session: Session) -> None:
    """Identify and delete duplicated statistics_meta.

    This is used when migrating from schema version 28 to schema version 29.
    """
    deleted_statistics_rows = _delete_statistics_meta_duplicates(session)
    if deleted_statistics_rows:
        _LOGGER.info(
            "Deleted %s duplicated statistics_meta rows", deleted_statistics_rows
        )


def _compile_hourly_statistics_summary_mean_stmt(
    start_time: datetime, end_time: datetime
) -> StatementLambdaElement:
    """Generate the summary mean statement for hourly statistics."""
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS_SUMMARY_MEAN)
        .filter(StatisticsShortTerm.start >= start_time)
        .filter(StatisticsShortTerm.start < end_time)
        .group_by(StatisticsShortTerm.metadata_id)
        .order_by(StatisticsShortTerm.metadata_id)
    )


def _compile_hourly_statistics(session: Session, start: datetime) -> None:
    """Compile hourly statistics.

    This will summarize 5-minute statistics for one hour:
    - average, min max is computed by a database query
    - sum is taken from the last 5-minute entry during the hour
    """
    start_time = start.replace(minute=0)
    end_time = start_time + timedelta(hours=1)

    # Compute last hour's average, min, max
    summary: dict[str, StatisticData] = {}
    stmt = _compile_hourly_statistics_summary_mean_stmt(start_time, end_time)
    stats = execute_stmt_lambda_element(session, stmt)

    if stats:
        for stat in stats:
            metadata_id, _mean, _min, _max = stat
            summary[metadata_id] = {
                "start": start_time,
                "mean": _mean,
                "min": _min,
                "max": _max,
            }

    # Get last hour's last sum
    subquery = (
        session.query(*QUERY_STATISTICS_SUMMARY_SUM)
        .filter(StatisticsShortTerm.start >= bindparam("start_time"))
        .filter(StatisticsShortTerm.start < bindparam("end_time"))
        .subquery()
    )
    query = (
        session.query(subquery)
        .filter(subquery.c.rownum == 1)
        .order_by(subquery.c.metadata_id)
    )
    stats = execute(query.params(start_time=start_time, end_time=end_time))

    if stats:
        for stat in stats:
            metadata_id, start, last_reset, state, _sum, _ = stat
            if metadata_id in summary:
                summary[metadata_id].update(
                    {
                        "last_reset": process_timestamp(last_reset),
                        "state": state,
                        "sum": _sum,
                    }
                )
            else:
                summary[metadata_id] = {
                    "start": start_time,
                    "last_reset": process_timestamp(last_reset),
                    "state": state,
                    "sum": _sum,
                }

    # Insert compiled hourly statistics in the database
    for metadata_id, stat in summary.items():
        session.add(Statistics.from_stats(metadata_id, stat))


@retryable_database_job("statistics")
def compile_statistics(instance: Recorder, start: datetime) -> bool:
    """Compile 5-minute statistics for all integrations with a recorder platform.

    The actual calculation is delegated to the platforms.
    """
    start = dt_util.as_utc(start)
    end = start + timedelta(minutes=5)

    # Return if we already have 5-minute statistics for the requested period
    with session_scope(session=instance.get_session()) as session:
        if session.query(StatisticsRuns).filter_by(start=start).first():
            _LOGGER.debug("Statistics already compiled for %s-%s", start, end)
            return True

    _LOGGER.debug("Compiling statistics for %s-%s", start, end)
    platform_stats: list[StatisticResult] = []
    current_metadata: dict[str, tuple[int, StatisticMetaData]] = {}
    # Collect statistics from all platforms implementing support
    for domain, platform in instance.hass.data[DOMAIN].recorder_platforms.items():
        if not hasattr(platform, "compile_statistics"):
            continue
        compiled: PlatformCompiledStatistics = platform.compile_statistics(
            instance.hass, start, end
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

    # Insert collected statistics in the database
    with session_scope(
        session=instance.get_session(),
        exception_filter=_filter_unique_constraint_integrity_error(instance),
    ) as session:
        for stats in platform_stats:
            metadata_id = _update_or_add_metadata(
                session, stats["meta"], current_metadata
            )
            _insert_statistics(
                session,
                StatisticsShortTerm,
                metadata_id,
                stats["stat"],
            )

        if start.minute == 55:
            # A full hour is ready, summarize it
            _compile_hourly_statistics(session, start)

        session.add(StatisticsRuns(start=start))

    return True


def _adjust_sum_statistics(
    session: Session,
    table: type[Statistics | StatisticsShortTerm],
    metadata_id: int,
    start_time: datetime,
    adj: float,
) -> None:
    """Adjust statistics in the database."""
    try:
        session.query(table).filter_by(metadata_id=metadata_id).filter(
            table.start >= start_time
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
    table: type[Statistics | StatisticsShortTerm],
    metadata_id: int,
    statistic: StatisticData,
) -> None:
    """Insert statistics in the database."""
    try:
        session.add(table.from_stats(metadata_id, statistic))
    except SQLAlchemyError:
        _LOGGER.exception(
            "Unexpected exception when inserting statistics %s:%s ",
            metadata_id,
            statistic,
        )


def _update_statistics(
    session: Session,
    table: type[Statistics | StatisticsShortTerm],
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
                table.last_reset: statistic.get("last_reset"),
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


def _generate_get_metadata_stmt(
    statistic_ids: list[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
    statistic_source: str | None = None,
) -> StatementLambdaElement:
    """Generate a statement to fetch metadata."""
    stmt = lambda_stmt(lambda: select(*QUERY_STATISTIC_META))
    if statistic_ids is not None:
        stmt += lambda q: q.where(StatisticsMeta.statistic_id.in_(statistic_ids))
    if statistic_source is not None:
        stmt += lambda q: q.where(StatisticsMeta.source == statistic_source)
    if statistic_type == "mean":
        stmt += lambda q: q.where(StatisticsMeta.has_mean == true())
    elif statistic_type == "sum":
        stmt += lambda q: q.where(StatisticsMeta.has_sum == true())
    return stmt


def get_metadata_with_session(
    session: Session,
    *,
    statistic_ids: list[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
    statistic_source: str | None = None,
) -> dict[str, tuple[int, StatisticMetaData]]:
    """Fetch meta data.

    Returns a dict of (metadata_id, StatisticMetaData) tuples indexed by statistic_id.

    If statistic_ids is given, fetch metadata only for the listed statistics_ids.
    If statistic_type is given, fetch metadata only for statistic_ids supporting it.
    """

    # Fetch metatadata from the database
    stmt = _generate_get_metadata_stmt(statistic_ids, statistic_type, statistic_source)
    result = execute_stmt_lambda_element(session, stmt)
    if not result:
        return {}

    return {
        meta["statistic_id"]: (
            meta["id"],
            {
                "has_mean": meta["has_mean"],
                "has_sum": meta["has_sum"],
                "name": meta["name"],
                "source": meta["source"],
                "statistic_id": meta["statistic_id"],
                "unit_of_measurement": meta["unit_of_measurement"],
            },
        )
        for meta in result
    }


def get_metadata(
    hass: HomeAssistant,
    *,
    statistic_ids: list[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
    statistic_source: str | None = None,
) -> dict[str, tuple[int, StatisticMetaData]]:
    """Return metadata for statistic_ids."""
    with session_scope(hass=hass) as session:
        return get_metadata_with_session(
            session,
            statistic_ids=statistic_ids,
            statistic_type=statistic_type,
            statistic_source=statistic_source,
        )


def clear_statistics(instance: Recorder, statistic_ids: list[str]) -> None:
    """Clear statistics for a list of statistic_ids."""
    with session_scope(session=instance.get_session()) as session:
        session.query(StatisticsMeta).filter(
            StatisticsMeta.statistic_id.in_(statistic_ids)
        ).delete(synchronize_session=False)


def update_statistics_metadata(
    instance: Recorder,
    statistic_id: str,
    new_statistic_id: str | None | UndefinedType,
    new_unit_of_measurement: str | None | UndefinedType,
) -> None:
    """Update statistics metadata for a statistic_id."""
    if new_unit_of_measurement is not UNDEFINED:
        with session_scope(session=instance.get_session()) as session:
            session.query(StatisticsMeta).filter(
                StatisticsMeta.statistic_id == statistic_id
            ).update({StatisticsMeta.unit_of_measurement: new_unit_of_measurement})
    if new_statistic_id is not UNDEFINED:
        with session_scope(
            session=instance.get_session(),
            exception_filter=_filter_unique_constraint_integrity_error(instance),
        ) as session:
            session.query(StatisticsMeta).filter(
                (StatisticsMeta.statistic_id == statistic_id)
                & (StatisticsMeta.source == DOMAIN)
            ).update({StatisticsMeta.statistic_id: new_statistic_id})


def list_statistic_ids(
    hass: HomeAssistant,
    statistic_ids: list[str] | None = None,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
) -> list[dict]:
    """Return all statistic_ids (or filtered one) and unit of measurement.

    Queries the database for existing statistic_ids, as well as integrations with
    a recorder platform for statistic_ids which will be added in the next statistics
    period.
    """
    result = {}

    # Query the database
    with session_scope(hass=hass) as session:
        metadata = get_metadata_with_session(
            session, statistic_type=statistic_type, statistic_ids=statistic_ids
        )

        result = {
            meta["statistic_id"]: {
                "has_mean": meta["has_mean"],
                "has_sum": meta["has_sum"],
                "name": meta["name"],
                "source": meta["source"],
                "unit_class": _get_unit_class(meta["unit_of_measurement"]),
                "unit_of_measurement": meta["unit_of_measurement"],
            }
            for _, meta in metadata.values()
        }

    # Query all integrations with a registered recorder platform
    for platform in hass.data[DOMAIN].recorder_platforms.values():
        if not hasattr(platform, "list_statistic_ids"):
            continue
        platform_statistic_ids = platform.list_statistic_ids(
            hass, statistic_ids=statistic_ids, statistic_type=statistic_type
        )

        for key, meta in platform_statistic_ids.items():
            if key in result:
                continue
            result[key] = {
                "has_mean": meta["has_mean"],
                "has_sum": meta["has_sum"],
                "name": meta["name"],
                "source": meta["source"],
                "unit_class": _get_unit_class(meta["unit_of_measurement"]),
                "unit_of_measurement": meta["unit_of_measurement"],
            }

    # Return a list of statistic_id + metadata
    return [
        {
            "statistic_id": _id,
            "has_mean": info["has_mean"],
            "has_sum": info["has_sum"],
            "name": info.get("name"),
            "source": info["source"],
            "statistics_unit_of_measurement": info["unit_of_measurement"],
            "unit_class": info["unit_class"],
        }
        for _id, info in result.items()
    ]


def _reduce_statistics(
    stats: dict[str, list[dict[str, Any]]],
    same_period: Callable[[datetime, datetime], bool],
    period_start_end: Callable[[datetime], tuple[datetime, datetime]],
    period: timedelta,
) -> dict[str, list[dict[str, Any]]]:
    """Reduce hourly statistics to daily or monthly statistics."""
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for statistic_id, stat_list in stats.items():
        max_values: list[float] = []
        mean_values: list[float] = []
        min_values: list[float] = []
        prev_stat: dict[str, Any] = stat_list[0]

        # Loop over the hourly statistics + a fake entry to end the period
        for statistic in chain(
            stat_list, ({"start": stat_list[-1]["start"] + period},)
        ):
            if not same_period(prev_stat["start"], statistic["start"]):
                start, end = period_start_end(prev_stat["start"])
                # The previous statistic was the last entry of the period
                result[statistic_id].append(
                    {
                        "statistic_id": statistic_id,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "mean": mean(mean_values) if mean_values else None,
                        "min": min(min_values) if min_values else None,
                        "max": max(max_values) if max_values else None,
                        "last_reset": prev_stat.get("last_reset"),
                        "state": prev_stat.get("state"),
                        "sum": prev_stat["sum"],
                    }
                )
                max_values = []
                mean_values = []
                min_values = []
            if statistic.get("max") is not None:
                max_values.append(statistic["max"])
            if statistic.get("mean") is not None:
                mean_values.append(statistic["mean"])
            if statistic.get("min") is not None:
                min_values.append(statistic["min"])
            prev_stat = statistic

    return result


def same_day(time1: datetime, time2: datetime) -> bool:
    """Return True if time1 and time2 are in the same date."""
    date1 = dt_util.as_local(time1).date()
    date2 = dt_util.as_local(time2).date()
    return date1 == date2


def day_start_end(time: datetime) -> tuple[datetime, datetime]:
    """Return the start and end of the period (day) time is within."""
    start = dt_util.as_utc(
        dt_util.as_local(time).replace(hour=0, minute=0, second=0, microsecond=0)
    )
    end = start + timedelta(days=1)
    return (start, end)


def _reduce_statistics_per_day(
    stats: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Reduce hourly statistics to daily statistics."""

    return _reduce_statistics(stats, same_day, day_start_end, timedelta(days=1))


def same_week(time1: datetime, time2: datetime) -> bool:
    """Return True if time1 and time2 are in the same year and week."""
    date1 = dt_util.as_local(time1).date()
    date2 = dt_util.as_local(time2).date()
    return (date1.year, date1.isocalendar().week) == (
        date2.year,
        date2.isocalendar().week,
    )


def week_start_end(time: datetime) -> tuple[datetime, datetime]:
    """Return the start and end of the period (week) time is within."""
    time_local = dt_util.as_local(time)
    start_local = time_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=time_local.weekday())
    start = dt_util.as_utc(start_local)
    end = dt_util.as_utc(start_local + timedelta(days=7))
    return (start, end)


def _reduce_statistics_per_week(
    stats: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Reduce hourly statistics to weekly statistics."""

    return _reduce_statistics(stats, same_week, week_start_end, timedelta(days=7))


def same_month(time1: datetime, time2: datetime) -> bool:
    """Return True if time1 and time2 are in the same year and month."""
    date1 = dt_util.as_local(time1).date()
    date2 = dt_util.as_local(time2).date()
    return (date1.year, date1.month) == (date2.year, date2.month)


def month_start_end(time: datetime) -> tuple[datetime, datetime]:
    """Return the start and end of the period (month) time is within."""
    start_local = dt_util.as_local(time).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    start = dt_util.as_utc(start_local)
    end_local = (start_local + timedelta(days=31)).replace(day=1)
    end = dt_util.as_utc(end_local)
    return (start, end)


def _reduce_statistics_per_month(
    stats: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Reduce hourly statistics to monthly statistics."""

    return _reduce_statistics(stats, same_month, month_start_end, timedelta(days=31))


def _statistics_during_period_stmt(
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
) -> StatementLambdaElement:
    """Prepare a database query for statistics during a given period.

    This prepares a lambda_stmt query, so we don't insert the parameters yet.
    """
    stmt = lambda_stmt(
        lambda: select(*QUERY_STATISTICS).filter(Statistics.start >= start_time)
    )
    if end_time is not None:
        stmt += lambda q: q.filter(Statistics.start < end_time)
    if metadata_ids:
        stmt += lambda q: q.filter(Statistics.metadata_id.in_(metadata_ids))
    stmt += lambda q: q.order_by(Statistics.metadata_id, Statistics.start)
    return stmt


def _statistics_during_period_stmt_short_term(
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
) -> StatementLambdaElement:
    """Prepare a database query for short term statistics during a given period.

    This prepares a lambda_stmt query, so we don't insert the parameters yet.
    """
    stmt = lambda_stmt(
        lambda: select(*QUERY_STATISTICS_SHORT_TERM).filter(
            StatisticsShortTerm.start >= start_time
        )
    )
    if end_time is not None:
        stmt += lambda q: q.filter(StatisticsShortTerm.start < end_time)
    if metadata_ids:
        stmt += lambda q: q.filter(StatisticsShortTerm.metadata_id.in_(metadata_ids))
    stmt += lambda q: q.order_by(
        StatisticsShortTerm.metadata_id, StatisticsShortTerm.start
    )
    return stmt


def _get_max_mean_min_statistic_in_sub_period(
    session: Session,
    result: dict[str, float],
    start_time: datetime | None,
    end_time: datetime | None,
    table: type[Statistics | StatisticsShortTerm],
    types: set[str],
    metadata_id: int,
) -> None:
    """Return max, mean and min during the period."""
    # Calculate max, mean, min
    columns = []
    if "max" in types:
        columns.append(func.max(table.max))
    if "mean" in types:
        columns.append(func.avg(table.mean))
        columns.append(func.count(table.mean))
    if "min" in types:
        columns.append(func.min(table.min))
    stmt = lambda_stmt(lambda: select(columns).filter(table.metadata_id == metadata_id))
    if start_time is not None:
        stmt += lambda q: q.filter(table.start >= start_time)
    if end_time is not None:
        stmt += lambda q: q.filter(table.start < end_time)
    stats = execute_stmt_lambda_element(session, stmt)
    if "max" in types and stats and (new_max := stats[0].max) is not None:
        old_max = result.get("max")
        result["max"] = max(new_max, old_max) if old_max is not None else new_max
    if "mean" in types and stats and stats[0].avg is not None:
        duration = stats[0].count * table.duration.total_seconds()
        result["duration"] = result.get("duration", 0.0) + duration
        result["mean_acc"] = result.get("mean_acc", 0.0) + stats[0].avg * duration
    if "min" in types and stats and (new_min := stats[0].min) is not None:
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
    types: set[str],
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


def _get_oldest_sum_statistic(
    session: Session,
    head_start_time: datetime | None,
    main_start_time: datetime | None,
    tail_start_time: datetime | None,
    tail_only: bool,
    metadata_id: int,
) -> float | None:
    """Return the oldest non-NULL sum during the period."""

    def _get_oldest_sum_statistic_in_sub_period(
        session: Session,
        start_time: datetime | None,
        table: type[Statistics | StatisticsShortTerm],
        metadata_id: int,
    ) -> tuple[float | None, datetime | None]:
        """Return the oldest non-NULL sum during the period."""
        stmt = lambda_stmt(
            lambda: select(table.sum, table.start)
            .filter(table.metadata_id == metadata_id)
            .filter(table.sum.is_not(None))
            .order_by(table.start.asc())
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
            stmt += lambda q: q.filter(table.start == prev_period)
        stats = execute_stmt_lambda_element(session, stmt)
        return (
            (stats[0].sum, process_timestamp(stats[0].start)) if stats else (None, None)
        )

    oldest_start: datetime | None
    oldest_sum: float | None = None

    if head_start_time is not None:
        oldest_sum, oldest_start = _get_oldest_sum_statistic_in_sub_period(
            session, head_start_time, StatisticsShortTerm, metadata_id
        )
        if (
            oldest_start is not None
            and oldest_start < head_start_time
            and oldest_sum is not None
        ):
            return oldest_sum

    if not tail_only:
        assert main_start_time is not None
        oldest_sum, oldest_start = _get_oldest_sum_statistic_in_sub_period(
            session, main_start_time, Statistics, metadata_id
        )
        if (
            oldest_start is not None
            and oldest_start < main_start_time
            and oldest_sum is not None
        ):
            return oldest_sum
        return 0

    if tail_start_time is not None:
        oldest_sum, oldest_start = _get_oldest_sum_statistic_in_sub_period(
            session, tail_start_time, StatisticsShortTerm, metadata_id
        )
        if (
            oldest_start is not None
            and oldest_start < tail_start_time
            and oldest_sum is not None
        ):
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
        table: type[Statistics | StatisticsShortTerm],
        metadata_id: int,
    ) -> float | None:
        """Return the newest non-NULL sum during the period."""
        stmt = lambda_stmt(
            lambda: select(
                table.sum,
            )
            .filter(table.metadata_id == metadata_id)
            .filter(table.sum.is_not(None))
            .order_by(table.start.desc())
            .limit(1)
        )
        if start_time is not None:
            stmt += lambda q: q.filter(table.start >= start_time)
        if end_time is not None:
            stmt += lambda q: q.filter(table.start < end_time)
        stats = execute_stmt_lambda_element(session, stmt)

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
    types: set[str] | None,
    units: dict[str, str] | None,
) -> dict[str, Any]:
    """Return a statistic data point for the UTC period start_time - end_time."""
    metadata = None

    if not types:
        types = {"max", "mean", "min", "change"}

    result: dict[str, Any] = {}

    # To calculate the summary, data from the statistics (hourly) and short_term_statistics
    # (5 minute) tables is combined
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
    if not tail_only and start_time is not None and start_time.minute:
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

    with session_scope(hass=hass) as session:
        # Fetch metadata for the given statistic_id
        metadata = get_metadata_with_session(session, statistic_ids=[statistic_id])
        if not metadata:
            return result

        metadata_id = metadata[statistic_id][0]

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

    def no_conversion(val: float | None) -> float | None:
        """Return val."""
        return val

    state_unit = unit = metadata[statistic_id][1]["unit_of_measurement"]
    if state := hass.states.get(statistic_id):
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit is not None:
        convert = _get_statistic_to_display_unit_converter(unit, state_unit, units)
    else:
        convert = no_conversion

    return {key: convert(value) for key, value in result.items()}


def statistics_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    statistic_ids: list[str] | None = None,
    period: Literal["5minute", "day", "hour", "week", "month"] = "hour",
    start_time_as_datetime: bool = False,
    units: dict[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return statistic data points during UTC period start_time - end_time.

    If end_time is omitted, returns statistics newer than or equal to start_time.
    If statistic_ids is omitted, returns statistics for all statistics ids.
    """
    metadata = None
    with session_scope(hass=hass) as session:
        # Fetch metadata for the given (or all) statistic_ids
        metadata = get_metadata_with_session(session, statistic_ids=statistic_ids)
        if not metadata:
            return {}

        metadata_ids = None
        if statistic_ids is not None:
            metadata_ids = [metadata_id for metadata_id, _ in metadata.values()]

        if period == "5minute":
            table = StatisticsShortTerm
            stmt = _statistics_during_period_stmt_short_term(
                start_time, end_time, metadata_ids
            )
        else:
            table = Statistics
            stmt = _statistics_during_period_stmt(start_time, end_time, metadata_ids)
        stats = execute_stmt_lambda_element(session, stmt)

        if not stats:
            return {}
        # Return statistics combined with metadata
        if period not in ("day", "week", "month"):
            return _sorted_statistics_to_dict(
                hass,
                session,
                stats,
                statistic_ids,
                metadata,
                True,
                table,
                start_time,
                start_time_as_datetime,
                units,
            )

        result = _sorted_statistics_to_dict(
            hass,
            session,
            stats,
            statistic_ids,
            metadata,
            True,
            table,
            start_time,
            True,
            units,
        )

        if period == "day":
            return _reduce_statistics_per_day(result)

        if period == "week":
            return _reduce_statistics_per_week(result)

        return _reduce_statistics_per_month(result)


def _get_last_statistics_stmt(
    metadata_id: int,
    number_of_stats: int,
) -> StatementLambdaElement:
    """Generate a statement for number_of_stats statistics for a given statistic_id."""
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS)
        .filter_by(metadata_id=metadata_id)
        .order_by(Statistics.metadata_id, Statistics.start.desc())
        .limit(number_of_stats)
    )


def _get_last_statistics_short_term_stmt(
    metadata_id: int,
    number_of_stats: int,
) -> StatementLambdaElement:
    """Generate a statement for number_of_stats short term statistics for a given statistic_id."""
    return lambda_stmt(
        lambda: select(*QUERY_STATISTICS_SHORT_TERM)
        .filter_by(metadata_id=metadata_id)
        .order_by(StatisticsShortTerm.metadata_id, StatisticsShortTerm.start.desc())
        .limit(number_of_stats)
    )


def _get_last_statistics(
    hass: HomeAssistant,
    number_of_stats: int,
    statistic_id: str,
    convert_units: bool,
    table: type[Statistics | StatisticsShortTerm],
) -> dict[str, list[dict]]:
    """Return the last number_of_stats statistics for a given statistic_id."""
    statistic_ids = [statistic_id]
    with session_scope(hass=hass) as session:
        # Fetch metadata for the given statistic_id
        metadata = get_metadata_with_session(session, statistic_ids=statistic_ids)
        if not metadata:
            return {}
        metadata_id = metadata[statistic_id][0]
        if table == Statistics:
            stmt = _get_last_statistics_stmt(metadata_id, number_of_stats)
        else:
            stmt = _get_last_statistics_short_term_stmt(metadata_id, number_of_stats)
        stats = execute_stmt_lambda_element(session, stmt)

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
            False,
            None,
        )


def get_last_statistics(
    hass: HomeAssistant, number_of_stats: int, statistic_id: str, convert_units: bool
) -> dict[str, list[dict]]:
    """Return the last number_of_stats statistics for a statistic_id."""
    return _get_last_statistics(
        hass, number_of_stats, statistic_id, convert_units, Statistics
    )


def get_last_short_term_statistics(
    hass: HomeAssistant, number_of_stats: int, statistic_id: str, convert_units: bool
) -> dict[str, list[dict]]:
    """Return the last number_of_stats short term statistics for a statistic_id."""
    return _get_last_statistics(
        hass, number_of_stats, statistic_id, convert_units, StatisticsShortTerm
    )


def _generate_most_recent_statistic_row(metadata_ids: list[int]) -> Subquery:
    """Generate the subquery to find the most recent statistic row."""
    return (
        select(
            StatisticsShortTerm.metadata_id,
            func.max(StatisticsShortTerm.start).label("start_max"),
        )
        .where(StatisticsShortTerm.metadata_id.in_(metadata_ids))
        .group_by(StatisticsShortTerm.metadata_id)
    ).subquery()


def _latest_short_term_statistics_stmt(
    metadata_ids: list[int],
) -> StatementLambdaElement:
    """Create the statement for finding the latest short term stat rows."""
    stmt = lambda_stmt(lambda: select(*QUERY_STATISTICS_SHORT_TERM))
    most_recent_statistic_row = _generate_most_recent_statistic_row(metadata_ids)
    stmt += lambda s: s.join(
        most_recent_statistic_row,
        (
            StatisticsShortTerm.metadata_id  # pylint: disable=comparison-with-callable
            == most_recent_statistic_row.c.metadata_id
        )
        & (StatisticsShortTerm.start == most_recent_statistic_row.c.start_max),
    )
    return stmt


def get_latest_short_term_statistics(
    hass: HomeAssistant,
    statistic_ids: list[str],
    metadata: dict[str, tuple[int, StatisticMetaData]] | None = None,
) -> dict[str, list[dict]]:
    """Return the latest short term statistics for a list of statistic_ids."""
    with session_scope(hass=hass) as session:
        # Fetch metadata for the given statistic_ids
        if not metadata:
            metadata = get_metadata_with_session(session, statistic_ids=statistic_ids)
        if not metadata:
            return {}
        metadata_ids = [
            metadata[statistic_id][0]
            for statistic_id in statistic_ids
            if statistic_id in metadata
        ]
        stmt = _latest_short_term_statistics_stmt(metadata_ids)
        stats = execute_stmt_lambda_element(session, stmt)
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
            False,
            None,
        )


def _statistics_at_time(
    session: Session,
    metadata_ids: set[int],
    table: type[Statistics | StatisticsShortTerm],
    start_time: datetime,
) -> list | None:
    """Return last known statistics, earlier than start_time, for the metadata_ids."""
    # Fetch metadata for the given (or all) statistic_ids
    if table == StatisticsShortTerm:
        base_query = QUERY_STATISTICS_SHORT_TERM
    else:
        base_query = QUERY_STATISTICS

    query = session.query(*base_query)

    most_recent_statistic_ids = (
        session.query(
            func.max(table.id).label("max_id"),
        )
        .filter(table.start < start_time)
        .filter(table.metadata_id.in_(metadata_ids))
    )
    most_recent_statistic_ids = most_recent_statistic_ids.group_by(table.metadata_id)
    most_recent_statistic_ids = most_recent_statistic_ids.subquery()
    query = query.join(
        most_recent_statistic_ids,
        table.id == most_recent_statistic_ids.c.max_id,
    )

    return execute(query)


def _sorted_statistics_to_dict(
    hass: HomeAssistant,
    session: Session,
    stats: Iterable[Row],
    statistic_ids: list[str] | None,
    _metadata: dict[str, tuple[int, StatisticMetaData]],
    convert_units: bool,
    table: type[Statistics | StatisticsShortTerm],
    start_time: datetime | None,
    start_time_as_datetime: bool,
    units: dict[str, str] | None,
) -> dict[str, list[dict]]:
    """Convert SQL results into JSON friendly data structure."""
    result: dict = defaultdict(list)
    metadata = dict(_metadata.values())
    need_stat_at_start_time: set[int] = set()
    stats_at_start_time = {}

    def no_conversion(val: float | None) -> float | None:
        """Return val."""
        return val

    # Set all statistic IDs to empty lists in result set to maintain the order
    if statistic_ids is not None:
        for stat_id in statistic_ids:
            result[stat_id] = []

    # Identify metadata IDs for which no data was available at the requested start time
    for meta_id, group in groupby(stats, lambda stat: stat.metadata_id):  # type: ignore[no-any-return]
        first_start_time = process_timestamp(next(group).start)
        if start_time and first_start_time > start_time:
            need_stat_at_start_time.add(meta_id)

    # Fetch last known statistics for the needed metadata IDs
    if need_stat_at_start_time:
        assert start_time  # Can not be None if need_stat_at_start_time is not empty
        tmp = _statistics_at_time(session, need_stat_at_start_time, table, start_time)
        if tmp:
            for stat in tmp:
                stats_at_start_time[stat.metadata_id] = (stat,)

    # Append all statistic entries, and optionally do unit conversion
    for meta_id, group in groupby(stats, lambda stat: stat.metadata_id):  # type: ignore[no-any-return]
        state_unit = unit = metadata[meta_id]["unit_of_measurement"]
        statistic_id = metadata[meta_id]["statistic_id"]
        if state := hass.states.get(statistic_id):
            state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit is not None and convert_units:
            convert = _get_statistic_to_display_unit_converter(unit, state_unit, units)
        else:
            convert = no_conversion
        ent_results = result[meta_id]
        for db_state in chain(stats_at_start_time.get(meta_id, ()), group):
            start = process_timestamp(db_state.start)
            end = start + table.duration
            ent_results.append(
                {
                    "statistic_id": statistic_id,
                    "start": start if start_time_as_datetime else start.isoformat(),
                    "end": end.isoformat(),
                    "mean": convert(db_state.mean),
                    "min": convert(db_state.min),
                    "max": convert(db_state.max),
                    "last_reset": process_timestamp_to_utc_isoformat(
                        db_state.last_reset
                    ),
                    "state": convert(db_state.state),
                    "sum": convert(db_state.sum),
                }
            )

    # Filter out the empty lists if some states had 0 results.
    return {metadata[key]["statistic_id"]: val for key, val in result.items() if val}


def validate_statistics(hass: HomeAssistant) -> dict[str, list[ValidationIssue]]:
    """Validate statistics."""
    platform_validation: dict[str, list[ValidationIssue]] = {}
    for platform in hass.data[DOMAIN].recorder_platforms.values():
        if not hasattr(platform, "validate_statistics"):
            continue
        platform_validation.update(platform.validate_statistics(hass))
    return platform_validation


def _statistics_exists(
    session: Session,
    table: type[Statistics | StatisticsShortTerm],
    metadata_id: int,
    start: datetime,
) -> int | None:
    """Return id if a statistics entry already exists."""
    result = (
        session.query(table.id)
        .filter((table.metadata_id == metadata_id) & (table.start == start))
        .first()
    )
    return result["id"] if result else None


@callback
def _async_import_statistics(
    hass: HomeAssistant,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
) -> None:
    """Validate timestamps and insert an import_statistics job in the recorder's queue."""
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
            and hasattr(err.orig, "pgcode")
            and err.orig.pgcode == "23505"
        ):
            ignore = True
        if dialect_name == SupportedDialect.MYSQL and hasattr(err.orig, "args"):
            with contextlib.suppress(TypeError):
                if err.orig.args[0] == 1062:
                    ignore = True

        if ignore:
            _LOGGER.warning(
                "Blocked attempt to insert duplicated statistic rows, please report at %s",
                "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+recorder%22",
                exc_info=err,
            )

        return ignore

    return _filter_unique_constraint_integrity_error


@retryable_database_job("statistics")
def import_statistics(
    instance: Recorder,
    metadata: StatisticMetaData,
    statistics: Iterable[StatisticData],
    table: type[Statistics | StatisticsShortTerm],
) -> bool:
    """Process an import_statistics job."""

    with session_scope(
        session=instance.get_session(),
        exception_filter=_filter_unique_constraint_integrity_error(instance),
    ) as session:
        old_metadata_dict = get_metadata_with_session(
            session, statistic_ids=[metadata["statistic_id"]]
        )
        metadata_id = _update_or_add_metadata(session, metadata, old_metadata_dict)
        for stat in statistics:
            if stat_id := _statistics_exists(
                session, table, metadata_id, stat["start"]
            ):
                _update_statistics(session, table, stat_id, stat)
            else:
                _insert_statistics(session, table, metadata_id, stat)

    return True


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
        metadata = get_metadata_with_session(session, statistic_ids=[statistic_id])
        if statistic_id not in metadata:
            return True

        statistic_unit = metadata[statistic_id][1]["unit_of_measurement"]
        convert = _get_display_to_statistic_unit_converter(
            adjustment_unit, statistic_unit
        )
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
    columns = [table.id, table.mean, table.min, table.max, table.state, table.sum]
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
    with session_scope(session=instance.get_session()) as session:
        metadata = get_metadata_with_session(session, statistic_ids=[statistic_id]).get(
            statistic_id
        )

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

        convert = _get_unit_converter(old_unit, new_unit)
        for table in (StatisticsShortTerm, Statistics):
            _change_statistics_unit_for_table(session, table, metadata_id, convert)
        session.query(StatisticsMeta).filter(
            StatisticsMeta.statistic_id == statistic_id
        ).update({StatisticsMeta.unit_of_measurement: new_unit})


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
