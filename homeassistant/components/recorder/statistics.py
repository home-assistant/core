"""Statistics helper."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
import dataclasses
from datetime import datetime, timedelta
from itertools import groupby
import logging
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import bindparam, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext import baked
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.sql.expression import true

from homeassistant.const import (
    PRESSURE_PA,
    TEMP_CELSIUS,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry
import homeassistant.util.dt as dt_util
import homeassistant.util.pressure as pressure_util
import homeassistant.util.temperature as temperature_util
from homeassistant.util.unit_system import UnitSystem
import homeassistant.util.volume as volume_util

from .const import DOMAIN
from .models import (
    StatisticData,
    StatisticMetaData,
    StatisticResult,
    Statistics,
    StatisticsMeta,
    StatisticsRuns,
    StatisticsShortTerm,
    process_timestamp,
    process_timestamp_to_utc_isoformat,
)
from .util import execute, retryable_database_job, session_scope

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

QUERY_STATISTICS_SUMMARY_SUM_LEGACY = [
    StatisticsShortTerm.metadata_id,
    StatisticsShortTerm.last_reset,
    StatisticsShortTerm.state,
    StatisticsShortTerm.sum,
]

QUERY_STATISTIC_META = [
    StatisticsMeta.id,
    StatisticsMeta.statistic_id,
    StatisticsMeta.unit_of_measurement,
    StatisticsMeta.has_mean,
    StatisticsMeta.has_sum,
]

QUERY_STATISTIC_META_ID = [
    StatisticsMeta.id,
    StatisticsMeta.statistic_id,
]

STATISTICS_BAKERY = "recorder_statistics_bakery"
STATISTICS_META_BAKERY = "recorder_statistics_meta_bakery"
STATISTICS_SHORT_TERM_BAKERY = "recorder_statistics_short_term_bakery"


# Convert pressure and temperature statistics from the native unit used for statistics
# to the units configured by the user
UNIT_CONVERSIONS = {
    PRESSURE_PA: lambda x, units: pressure_util.convert(
        x, PRESSURE_PA, units.pressure_unit
    )
    if x is not None
    else None,
    TEMP_CELSIUS: lambda x, units: temperature_util.convert(
        x, TEMP_CELSIUS, units.temperature_unit
    )
    if x is not None
    else None,
    VOLUME_CUBIC_METERS: lambda x, units: volume_util.convert(
        x, VOLUME_CUBIC_METERS, _configured_unit(VOLUME_CUBIC_METERS, units)
    )
    if x is not None
    else None,
}

_LOGGER = logging.getLogger(__name__)


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
    hass.data[STATISTICS_BAKERY] = baked.bakery()
    hass.data[STATISTICS_META_BAKERY] = baked.bakery()
    hass.data[STATISTICS_SHORT_TERM_BAKERY] = baked.bakery()

    def entity_id_changed(event: Event) -> None:
        """Handle entity_id changed."""
        old_entity_id = event.data["old_entity_id"]
        entity_id = event.data["entity_id"]
        with session_scope(hass=hass) as session:
            session.query(StatisticsMeta).filter(
                StatisticsMeta.statistic_id == old_entity_id
                and StatisticsMeta.source == DOMAIN
            ).update({StatisticsMeta.statistic_id: entity_id})

    @callback
    def entity_registry_changed_filter(event: Event) -> bool:
        """Handle entity_id changed filter."""
        if event.data["action"] != "update" or "old_entity_id" not in event.data:
            return False

        return True

    if hass.is_running:
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            entity_id_changed,
            event_filter=entity_registry_changed_filter,
        )


def get_start_time() -> datetime:
    """Return start time."""
    now = dt_util.utcnow()
    current_period_minutes = now.minute - now.minute % 5
    current_period = now.replace(minute=current_period_minutes, second=0, microsecond=0)
    last_period = current_period - timedelta(minutes=5)
    return last_period


def _update_or_add_metadata(
    hass: HomeAssistant,
    session: scoped_session,
    new_metadata: StatisticMetaData,
) -> int:
    """Get metadata_id for a statistic_id.

    If the statistic_id is previously unknown, add it. If it's already known, update
    metadata if needed.

    Updating metadata source is not possible.
    """
    statistic_id = new_metadata["statistic_id"]
    old_metadata_dict = get_metadata_with_session(hass, session, [statistic_id], None)
    if not old_metadata_dict:
        unit = new_metadata["unit_of_measurement"]
        has_mean = new_metadata["has_mean"]
        has_sum = new_metadata["has_sum"]
        meta = StatisticsMeta.from_meta(DOMAIN, statistic_id, unit, has_mean, has_sum)
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
        or old_metadata["unit_of_measurement"] != new_metadata["unit_of_measurement"]
    ):
        session.query(StatisticsMeta).filter_by(statistic_id=statistic_id).update(
            {
                StatisticsMeta.has_mean: new_metadata["has_mean"],
                StatisticsMeta.has_sum: new_metadata["has_sum"],
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


def compile_hourly_statistics(
    instance: Recorder, session: scoped_session, start: datetime
) -> None:
    """Compile hourly statistics.

    This will summarize 5-minute statistics for one hour:
    - average, min max is computed by a database query
    - sum is taken from the last 5-minute entry during the hour
    """
    start_time = start.replace(minute=0)
    end_time = start_time + timedelta(hours=1)

    # Compute last hour's average, min, max
    summary: dict[str, StatisticData] = {}
    baked_query = instance.hass.data[STATISTICS_SHORT_TERM_BAKERY](
        lambda session: session.query(*QUERY_STATISTICS_SUMMARY_MEAN)
    )

    baked_query += lambda q: q.filter(
        StatisticsShortTerm.start >= bindparam("start_time")
    )
    baked_query += lambda q: q.filter(StatisticsShortTerm.start < bindparam("end_time"))
    baked_query += lambda q: q.group_by(StatisticsShortTerm.metadata_id)
    baked_query += lambda q: q.order_by(StatisticsShortTerm.metadata_id)

    stats = execute(
        baked_query(session).params(start_time=start_time, end_time=end_time)
    )

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
    if instance._db_supports_row_number:  # pylint: disable=[protected-access]
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
    else:
        baked_query = instance.hass.data[STATISTICS_SHORT_TERM_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS_SUMMARY_SUM_LEGACY)
        )

        baked_query += lambda q: q.filter(
            StatisticsShortTerm.start >= bindparam("start_time")
        )
        baked_query += lambda q: q.filter(
            StatisticsShortTerm.start < bindparam("end_time")
        )
        baked_query += lambda q: q.order_by(
            StatisticsShortTerm.metadata_id, StatisticsShortTerm.start.desc()
        )

        stats = execute(
            baked_query(session).params(start_time=start_time, end_time=end_time)
        )

        if stats:
            for metadata_id, group in groupby(stats, lambda stat: stat["metadata_id"]):  # type: ignore
                (
                    metadata_id,
                    last_reset,
                    state,
                    _sum,
                ) = next(group)
                if metadata_id in summary:
                    summary[metadata_id].update(
                        {
                            "start": start_time,
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
    with session_scope(session=instance.get_session()) as session:  # type: ignore
        if session.query(StatisticsRuns).filter_by(start=start).first():
            _LOGGER.debug("Statistics already compiled for %s-%s", start, end)
            return True

    _LOGGER.debug("Compiling statistics for %s-%s", start, end)
    platform_stats: list[StatisticResult] = []
    # Collect statistics from all platforms implementing support
    for domain, platform in instance.hass.data[DOMAIN].items():
        if not hasattr(platform, "compile_statistics"):
            continue
        platform_stat = platform.compile_statistics(instance.hass, start, end)
        _LOGGER.debug(
            "Statistics for %s during %s-%s: %s", domain, start, end, platform_stat
        )
        platform_stats.extend(platform_stat)

    # Insert collected statistics in the database
    with session_scope(session=instance.get_session()) as session:  # type: ignore
        for stats in platform_stats:
            metadata_id = _update_or_add_metadata(instance.hass, session, stats["meta"])
            for stat in stats["stat"]:
                try:
                    session.add(StatisticsShortTerm.from_stats(metadata_id, stat))
                except SQLAlchemyError:
                    _LOGGER.exception(
                        "Unexpected exception when inserting statistics %s:%s ",
                        metadata_id,
                        stats,
                    )

        if start.minute == 55:
            # A full hour is ready, summarize it
            compile_hourly_statistics(instance, session, start)

        session.add(StatisticsRuns(start=start))

    return True


def get_metadata_with_session(
    hass: HomeAssistant,
    session: scoped_session,
    statistic_ids: Iterable[str] | None,
    statistic_type: Literal["mean"] | Literal["sum"] | None,
) -> dict[str, tuple[int, StatisticMetaData]]:
    """Fetch meta data.

    Returns a dict of (metadata_id, StatisticMetaData) indexed by statistic_id.

    If statistic_ids is given, fetch metadata only for the listed statistics_ids.
    If statistic_type is given, fetch metadata only for statistic_ids supporting it.
    """

    def _meta(metas: list, wanted_metadata_id: str) -> StatisticMetaData | None:
        meta: StatisticMetaData | None = None
        for metadata_id, statistic_id, unit, has_mean, has_sum in metas:
            if metadata_id == wanted_metadata_id:
                meta = {
                    "statistic_id": statistic_id,
                    "unit_of_measurement": unit,
                    "has_mean": has_mean,
                    "has_sum": has_sum,
                }
        return meta

    # Fetch metatadata from the database
    baked_query = hass.data[STATISTICS_META_BAKERY](
        lambda session: session.query(*QUERY_STATISTIC_META)
    )
    if statistic_ids is not None:
        baked_query += lambda q: q.filter(
            StatisticsMeta.statistic_id.in_(bindparam("statistic_ids"))
        )
    if statistic_type == "mean":
        baked_query += lambda q: q.filter(StatisticsMeta.has_mean == true())
    elif statistic_type == "sum":
        baked_query += lambda q: q.filter(StatisticsMeta.has_sum == true())
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))
    if not result:
        return {}

    metadata_ids = [metadata[0] for metadata in result]
    # Prepare the result dict
    metadata: dict[str, tuple[int, StatisticMetaData]] = {}
    for _id in metadata_ids:
        meta = _meta(result, _id)
        if meta:
            metadata[meta["statistic_id"]] = (_id, meta)
    return metadata


def get_metadata(
    hass: HomeAssistant,
    statistic_ids: Iterable[str],
) -> dict[str, tuple[int, StatisticMetaData]]:
    """Return metadata for statistic_ids."""
    with session_scope(hass=hass) as session:
        return get_metadata_with_session(hass, session, statistic_ids, None)


def _configured_unit(unit: str, units: UnitSystem) -> str:
    """Return the pressure and temperature units configured by the user."""
    if unit == PRESSURE_PA:
        return units.pressure_unit
    if unit == TEMP_CELSIUS:
        return units.temperature_unit
    if unit == VOLUME_CUBIC_METERS:
        if units.is_metric:
            return VOLUME_CUBIC_METERS
        return VOLUME_CUBIC_FEET
    return unit


def clear_statistics(instance: Recorder, statistic_ids: list[str]) -> None:
    """Clear statistics for a list of statistic_ids."""
    with session_scope(session=instance.get_session()) as session:  # type: ignore
        session.query(StatisticsMeta).filter(
            StatisticsMeta.statistic_id.in_(statistic_ids)
        ).delete(synchronize_session=False)


def update_statistics_metadata(
    instance: Recorder, statistic_id: str, unit_of_measurement: str | None
) -> None:
    """Update statistics metadata for a statistic_id."""
    with session_scope(session=instance.get_session()) as session:  # type: ignore
        session.query(StatisticsMeta).filter(
            StatisticsMeta.statistic_id == statistic_id
        ).update({StatisticsMeta.unit_of_measurement: unit_of_measurement})


def list_statistic_ids(
    hass: HomeAssistant,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
) -> list[dict | None]:
    """Return all statistic_ids and unit of measurement.

    Queries the database for existing statistic_ids, as well as integrations with
    a recorder platform for statistic_ids which will be added in the next statistics
    period.
    """
    units = hass.config.units
    statistic_ids = {}

    # Query the database
    with session_scope(hass=hass) as session:
        metadata = get_metadata_with_session(hass, session, None, statistic_type)

        for _, meta in metadata.values():
            unit = meta["unit_of_measurement"]
            if unit is not None:
                # Display unit according to user settings
                unit = _configured_unit(unit, units)
            meta["unit_of_measurement"] = unit

        statistic_ids = {
            meta["statistic_id"]: meta["unit_of_measurement"]
            for _, meta in metadata.values()
        }

    # Query all integrations with a registered recorder platform
    for platform in hass.data[DOMAIN].values():
        if not hasattr(platform, "list_statistic_ids"):
            continue
        platform_statistic_ids = platform.list_statistic_ids(hass, statistic_type)

        for statistic_id, unit in platform_statistic_ids.items():
            if unit is not None:
                # Display unit according to user settings
                unit = _configured_unit(unit, units)
            platform_statistic_ids[statistic_id] = unit

        for key, value in platform_statistic_ids.items():
            statistic_ids.setdefault(key, value)

    # Return a map of statistic_id to unit_of_measurement
    return [
        {"statistic_id": _id, "unit_of_measurement": unit}
        for _id, unit in statistic_ids.items()
    ]


def _statistics_during_period_query(
    hass: HomeAssistant,
    end_time: datetime | None,
    statistic_ids: list[str] | None,
    bakery: Any,
    base_query: Iterable,
    table: type[Statistics | StatisticsShortTerm],
) -> Callable:
    """Prepare a database query for statistics during a given period.

    This prepares a baked query, so we don't insert the parameters yet.
    """
    baked_query = hass.data[bakery](lambda session: session.query(*base_query))

    baked_query += lambda q: q.filter(table.start >= bindparam("start_time"))

    if end_time is not None:
        baked_query += lambda q: q.filter(table.start < bindparam("end_time"))

    if statistic_ids is not None:
        baked_query += lambda q: q.filter(
            table.metadata_id.in_(bindparam("metadata_ids"))
        )

    baked_query += lambda q: q.order_by(table.metadata_id, table.start)
    return baked_query  # type: ignore[no-any-return]


def statistics_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    statistic_ids: list[str] | None = None,
    period: Literal["hour"] | Literal["5minute"] = "hour",
) -> dict[str, list[dict[str, str]]]:
    """Return statistics during UTC period start_time - end_time for the statistic_ids.

    If end_time is omitted, returns statistics newer than or equal to start_time.
    If statistic_ids is omitted, returns statistics for all statistics ids.
    """
    metadata = None
    with session_scope(hass=hass) as session:
        # Fetch metadata for the given (or all) statistic_ids
        metadata = get_metadata_with_session(hass, session, statistic_ids, None)
        if not metadata:
            return {}

        metadata_ids = None
        if statistic_ids is not None:
            metadata_ids = [metadata_id for metadata_id, _ in metadata.values()]

        if period == "hour":
            bakery = STATISTICS_BAKERY
            base_query = QUERY_STATISTICS
            table = Statistics
        else:
            bakery = STATISTICS_SHORT_TERM_BAKERY
            base_query = QUERY_STATISTICS_SHORT_TERM
            table = StatisticsShortTerm

        baked_query = _statistics_during_period_query(
            hass, end_time, statistic_ids, bakery, base_query, table
        )

        stats = execute(
            baked_query(session).params(
                start_time=start_time, end_time=end_time, metadata_ids=metadata_ids
            )
        )
        if not stats:
            return {}
        # Return statistics combined with metadata
        return _sorted_statistics_to_dict(
            hass, stats, statistic_ids, metadata, True, table.duration
        )


def get_last_statistics(
    hass: HomeAssistant, number_of_stats: int, statistic_id: str, convert_units: bool
) -> dict[str, list[dict]]:
    """Return the last number_of_stats statistics for a given statistic_id."""
    statistic_ids = [statistic_id]
    with session_scope(hass=hass) as session:
        # Fetch metadata for the given statistic_id
        metadata = get_metadata_with_session(hass, session, statistic_ids, None)
        if not metadata:
            return {}

        baked_query = hass.data[STATISTICS_SHORT_TERM_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS_SHORT_TERM)
        )

        baked_query += lambda q: q.filter_by(metadata_id=bindparam("metadata_id"))
        metadata_id = metadata[statistic_id][0]

        baked_query += lambda q: q.order_by(
            StatisticsShortTerm.metadata_id, StatisticsShortTerm.start.desc()
        )

        baked_query += lambda q: q.limit(bindparam("number_of_stats"))

        stats = execute(
            baked_query(session).params(
                number_of_stats=number_of_stats, metadata_id=metadata_id
            )
        )
        if not stats:
            return {}

        # Return statistics combined with metadata
        return _sorted_statistics_to_dict(
            hass,
            stats,
            statistic_ids,
            metadata,
            convert_units,
            StatisticsShortTerm.duration,
        )


def _sorted_statistics_to_dict(
    hass: HomeAssistant,
    stats: list,
    statistic_ids: list[str] | None,
    _metadata: dict[str, tuple[int, StatisticMetaData]],
    convert_units: bool,
    duration: timedelta,
) -> dict[str, list[dict]]:
    """Convert SQL results into JSON friendly data structure."""
    result: dict = defaultdict(list)
    units = hass.config.units

    def no_conversion(val: Any, _: Any) -> float | None:
        """Return x."""
        return val  # type: ignore

    # Set all statistic IDs to empty lists in result set to maintain the order
    if statistic_ids is not None:
        for stat_id in statistic_ids:
            result[stat_id] = []

    metadata = dict(_metadata.values())

    # Append all statistic entries, and optionally do unit conversion
    for meta_id, group in groupby(stats, lambda stat: stat.metadata_id):  # type: ignore
        unit = metadata[meta_id]["unit_of_measurement"]
        statistic_id = metadata[meta_id]["statistic_id"]
        convert: Callable[[Any, Any], float | None]
        if convert_units:
            convert = UNIT_CONVERSIONS.get(unit, lambda x, units: x)  # type: ignore
        else:
            convert = no_conversion
        ent_results = result[meta_id]
        for db_state in group:
            start = process_timestamp(db_state.start)
            end = start + duration
            ent_results.append(
                {
                    "statistic_id": statistic_id,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "mean": convert(db_state.mean, units),
                    "min": convert(db_state.min, units),
                    "max": convert(db_state.max, units),
                    "last_reset": process_timestamp_to_utc_isoformat(
                        db_state.last_reset
                    ),
                    "state": convert(db_state.state, units),
                    "sum": convert(db_state.sum, units),
                }
            )

    # Filter out the empty lists if some states had 0 results.
    return {metadata[key]["statistic_id"]: val for key, val in result.items() if val}


def validate_statistics(hass: HomeAssistant) -> dict[str, list[ValidationIssue]]:
    """Validate statistics."""
    platform_validation: dict[str, list[ValidationIssue]] = {}
    for platform in hass.data[DOMAIN].values():
        if not hasattr(platform, "validate_statistics"):
            continue
        platform_validation.update(platform.validate_statistics(hass))
    return platform_validation
