"""Statistics helper."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import dataclasses
from datetime import datetime, timedelta
from itertools import groupby
import logging
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import bindparam, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext import baked
from sqlalchemy.orm.scoping import scoped_session

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
    StatisticMetaData,
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
    Statistics.sum_increase,
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
    StatisticsShortTerm.sum_increase,
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
    StatisticsShortTerm.sum_increase,
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


def _get_metadata_ids(
    hass: HomeAssistant, session: scoped_session, statistic_ids: list[str]
) -> list[str]:
    """Resolve metadata_id for a list of statistic_ids."""
    baked_query = hass.data[STATISTICS_META_BAKERY](
        lambda session: session.query(*QUERY_STATISTIC_META_ID)
    )
    baked_query += lambda q: q.filter(
        StatisticsMeta.statistic_id.in_(bindparam("statistic_ids"))
    )
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))

    return [id for id, _ in result] if result else []


def _update_or_add_metadata(
    hass: HomeAssistant,
    session: scoped_session,
    statistic_id: str,
    new_metadata: StatisticMetaData,
) -> str:
    """Get metadata_id for a statistic_id, add if it doesn't exist."""
    old_metadata_dict = _get_metadata(hass, session, [statistic_id], None)
    if not old_metadata_dict:
        unit = new_metadata["unit_of_measurement"]
        has_mean = new_metadata["has_mean"]
        has_sum = new_metadata["has_sum"]
        session.add(
            StatisticsMeta.from_meta(DOMAIN, statistic_id, unit, has_mean, has_sum)
        )
        metadata_ids = _get_metadata_ids(hass, session, [statistic_id])
        _LOGGER.debug(
            "Added new statistics metadata for %s, new_metadata: %s",
            statistic_id,
            new_metadata,
        )
        return metadata_ids[0]

    metadata_id, old_metadata = next(iter(old_metadata_dict.items()))
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
    """Compile hourly statistics."""
    start_time = start.replace(minute=0)
    end_time = start_time + timedelta(hours=1)
    # Get last hour's average, min, max
    summary = {}
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
                "metadata_id": metadata_id,
                "mean": _mean,
                "min": _min,
                "max": _max,
            }

    # Get last hour's sum
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
            metadata_id, start, last_reset, state, _sum, sum_increase, _ = stat
            summary[metadata_id] = {
                **summary.get(metadata_id, {}),
                **{
                    "metadata_id": metadata_id,
                    "last_reset": process_timestamp(last_reset),
                    "state": state,
                    "sum": _sum,
                    "sum_increase": sum_increase,
                },
            }

    for stat in summary.values():
        session.add(Statistics.from_stats(stat.pop("metadata_id"), start_time, stat))


@retryable_database_job("statistics")
def compile_statistics(instance: Recorder, start: datetime) -> bool:
    """Compile statistics."""
    start = dt_util.as_utc(start)
    end = start + timedelta(minutes=5)

    with session_scope(session=instance.get_session()) as session:  # type: ignore
        if session.query(StatisticsRuns).filter_by(start=start).first():
            _LOGGER.debug("Statistics already compiled for %s-%s", start, end)
            return True

    _LOGGER.debug("Compiling statistics for %s-%s", start, end)
    platform_stats = []
    for domain, platform in instance.hass.data[DOMAIN].items():
        if not hasattr(platform, "compile_statistics"):
            continue
        platform_stats.append(platform.compile_statistics(instance.hass, start, end))
        _LOGGER.debug(
            "Statistics for %s during %s-%s: %s", domain, start, end, platform_stats[-1]
        )

    with session_scope(session=instance.get_session()) as session:  # type: ignore
        for stats in platform_stats:
            for entity_id, stat in stats.items():
                metadata_id = _update_or_add_metadata(
                    instance.hass, session, entity_id, stat["meta"]
                )
                try:
                    session.add(
                        StatisticsShortTerm.from_stats(metadata_id, start, stat["stat"])
                    )
                except SQLAlchemyError:
                    _LOGGER.exception(
                        "Unexpected exception when inserting statistics %s:%s ",
                        metadata_id,
                        stat,
                    )

        if start.minute == 55:
            # A full hour is ready, summarize it
            compile_hourly_statistics(instance, session, start)

        session.add(StatisticsRuns(start=start))

    return True


def _get_metadata(
    hass: HomeAssistant,
    session: scoped_session,
    statistic_ids: list[str] | None,
    statistic_type: str | None,
) -> dict[str, StatisticMetaData]:
    """Fetch meta data."""

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

    baked_query = hass.data[STATISTICS_META_BAKERY](
        lambda session: session.query(*QUERY_STATISTIC_META)
    )
    if statistic_ids is not None:
        baked_query += lambda q: q.filter(
            StatisticsMeta.statistic_id.in_(bindparam("statistic_ids"))
        )
    if statistic_type == "mean":
        baked_query += lambda q: q.filter(StatisticsMeta.has_mean.isnot(False))
    elif statistic_type == "sum":
        baked_query += lambda q: q.filter(StatisticsMeta.has_sum.isnot(False))
    elif statistic_type is not None:
        return {}
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))
    if not result:
        return {}

    metadata_ids = [metadata[0] for metadata in result]
    metadata: dict[str, StatisticMetaData] = {}
    for _id in metadata_ids:
        meta = _meta(result, _id)
        if meta:
            metadata[_id] = meta
    return metadata


def get_metadata(
    hass: HomeAssistant,
    statistic_id: str,
) -> StatisticMetaData | None:
    """Return metadata for a statistic_id."""
    statistic_ids = [statistic_id]
    with session_scope(hass=hass) as session:
        metadata_ids = _get_metadata_ids(hass, session, [statistic_id])
        if not metadata_ids:
            return None
        return _get_metadata(hass, session, statistic_ids, None).get(metadata_ids[0])


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


def list_statistic_ids(
    hass: HomeAssistant, statistic_type: str | None = None
) -> list[StatisticMetaData | None]:
    """Return statistic_ids and meta data."""
    units = hass.config.units
    statistic_ids = {}
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, None, statistic_type)

        for meta in metadata.values():
            unit = meta["unit_of_measurement"]
            if unit is not None:
                unit = _configured_unit(unit, units)
            meta["unit_of_measurement"] = unit

        statistic_ids = {
            meta["statistic_id"]: meta["unit_of_measurement"]
            for meta in metadata.values()
        }

    for platform in hass.data[DOMAIN].values():
        if not hasattr(platform, "list_statistic_ids"):
            continue
        platform_statistic_ids = platform.list_statistic_ids(hass, statistic_type)

        for statistic_id, unit in platform_statistic_ids.items():
            if unit is not None:
                unit = _configured_unit(unit, units)
            platform_statistic_ids[statistic_id] = unit

        statistic_ids = {**statistic_ids, **platform_statistic_ids}

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
    period: str = "hour",
) -> dict[str, list[dict[str, str]]]:
    """Return states changes during UTC period start_time - end_time."""
    metadata = None
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, statistic_ids, None)
        if not metadata:
            return {}

        metadata_ids = None
        if statistic_ids is not None:
            metadata_ids = list(metadata.keys())

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
        return _sorted_statistics_to_dict(
            hass, stats, statistic_ids, metadata, True, table.duration
        )


def get_last_statistics(
    hass: HomeAssistant, number_of_stats: int, statistic_id: str, convert_units: bool
) -> dict[str, list[dict]]:
    """Return the last number_of_stats statistics for a statistic_id."""
    statistic_ids = [statistic_id]
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, statistic_ids, None)
        if not metadata:
            return {}

        baked_query = hass.data[STATISTICS_SHORT_TERM_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS_SHORT_TERM)
        )

        baked_query += lambda q: q.filter_by(metadata_id=bindparam("metadata_id"))
        metadata_id = next(iter(metadata.keys()))

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
    metadata: dict[str, StatisticMetaData],
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

    # Append all statistic entries, and do unit conversion
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
                    "sum": (_sum := convert(db_state.sum, units)),
                    "sum_increase": (inc := convert(db_state.sum_increase, units)),
                    "sum_decrease": None if _sum is None or inc is None else inc - _sum,
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
