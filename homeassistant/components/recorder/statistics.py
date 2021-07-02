"""Statistics helper."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import groupby
import logging
from typing import TYPE_CHECKING

from sqlalchemy import bindparam
from sqlalchemy.ext import baked

from homeassistant.const import PRESSURE_PA, TEMP_CELSIUS
import homeassistant.util.dt as dt_util
import homeassistant.util.pressure as pressure_util
import homeassistant.util.temperature as temperature_util

from .const import DOMAIN
from .models import Statistics, StatisticsMeta, process_timestamp_to_utc_isoformat
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

QUERY_STATISTIC_META = [
    StatisticsMeta.id,
    StatisticsMeta.statistic_id,
    StatisticsMeta.unit_of_measurement,
]

STATISTICS_BAKERY = "recorder_statistics_bakery"
STATISTICS_META_BAKERY = "recorder_statistics_bakery"

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
}

_LOGGER = logging.getLogger(__name__)


def async_setup(hass):
    """Set up the history hooks."""
    hass.data[STATISTICS_BAKERY] = baked.bakery()
    hass.data[STATISTICS_META_BAKERY] = baked.bakery()


def get_start_time() -> datetime.datetime:
    """Return start time."""
    last_hour = dt_util.utcnow() - timedelta(hours=1)
    start = last_hour.replace(minute=0, second=0, microsecond=0)
    return start


def _get_metadata_ids(hass, session, statistic_ids):
    """Resolve metadata_id for a list of statistic_ids."""
    baked_query = hass.data[STATISTICS_META_BAKERY](
        lambda session: session.query(*QUERY_STATISTIC_META)
    )
    baked_query += lambda q: q.filter(
        StatisticsMeta.statistic_id.in_(bindparam("statistic_ids"))
    )
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))

    return [id for id, _, _ in result]


def _get_or_add_metadata_id(hass, session, statistic_id, metadata):
    """Get metadata_id for a statistic_id, add if it doesn't exist."""
    metadata_id = _get_metadata_ids(hass, session, [statistic_id])
    if not metadata_id:
        unit = metadata["unit_of_measurement"]
        has_mean = metadata["has_mean"]
        has_sum = metadata["has_sum"]
        session.add(
            StatisticsMeta.from_meta(DOMAIN, statistic_id, unit, has_mean, has_sum)
        )
        metadata_id = _get_metadata_ids(hass, session, [statistic_id])
    return metadata_id[0]


@retryable_database_job("statistics")
def compile_statistics(instance: Recorder, start: datetime.datetime) -> bool:
    """Compile statistics."""
    start = dt_util.as_utc(start)
    end = start + timedelta(hours=1)
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
                metadata_id = _get_or_add_metadata_id(
                    instance.hass, session, entity_id, stat["meta"]
                )
                session.add(Statistics.from_stats(metadata_id, start, stat["stat"]))

    return True


def _get_metadata(hass, session, statistic_ids, statistic_type):
    """Fetch meta data."""

    def _meta(metas, wanted_metadata_id):
        meta = None
        for metadata_id, statistic_id, unit in metas:
            if metadata_id == wanted_metadata_id:
                meta = {"unit_of_measurement": unit, "statistic_id": statistic_id}
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
    if statistic_type == "sum":
        baked_query += lambda q: q.filter(StatisticsMeta.has_sum.isnot(False))
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))

    metadata_ids = [metadata[0] for metadata in result]
    return {id: _meta(result, id) for id in metadata_ids}


def _configured_unit(unit: str, units) -> str:
    """Return the pressure and temperature units configured by the user."""
    if unit == PRESSURE_PA:
        return units.pressure_unit
    if unit == TEMP_CELSIUS:
        return units.temperature_unit
    return unit


def list_statistic_ids(hass, statistic_type=None):
    """Return statistic_ids and meta data."""
    units = hass.config.units
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, None, statistic_type)

        for meta in metadata.values():
            unit = _configured_unit(meta["unit_of_measurement"], units)
            meta["unit_of_measurement"] = unit

        return list(metadata.values())


def statistics_during_period(hass, start_time, end_time=None, statistic_ids=None):
    """Return states changes during UTC period start_time - end_time."""
    metadata = None
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, statistic_ids, None)
        if not metadata:
            return {}

        baked_query = hass.data[STATISTICS_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS)
        )

        baked_query += lambda q: q.filter(Statistics.start >= bindparam("start_time"))

        if end_time is not None:
            baked_query += lambda q: q.filter(Statistics.start < bindparam("end_time"))

        metadata_ids = None
        if statistic_ids is not None:
            baked_query += lambda q: q.filter(
                Statistics.metadata_id.in_(bindparam("metadata_ids"))
            )
            metadata_ids = list(metadata.keys())

        baked_query += lambda q: q.order_by(Statistics.metadata_id, Statistics.start)

        stats = execute(
            baked_query(session).params(
                start_time=start_time, end_time=end_time, metadata_ids=metadata_ids
            )
        )
        return _sorted_statistics_to_dict(hass, stats, statistic_ids, metadata)


def get_last_statistics(hass, number_of_stats, statistic_id):
    """Return the last number_of_stats statistics for a statistic_id."""
    statistic_ids = [statistic_id]
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, statistic_ids, None)
        if not metadata:
            return {}

        baked_query = hass.data[STATISTICS_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS)
        )

        baked_query += lambda q: q.filter_by(metadata_id=bindparam("metadata_id"))
        metadata_id = next(iter(metadata.keys()))

        baked_query += lambda q: q.order_by(
            Statistics.metadata_id, Statistics.start.desc()
        )

        baked_query += lambda q: q.limit(bindparam("number_of_stats"))

        stats = execute(
            baked_query(session).params(
                number_of_stats=number_of_stats, metadata_id=metadata_id
            )
        )

        return _sorted_statistics_to_dict(hass, stats, statistic_ids, metadata)


def _sorted_statistics_to_dict(
    hass,
    stats,
    statistic_ids,
    metadata,
):
    """Convert SQL results into JSON friendly data structure."""
    result = defaultdict(list)
    units = hass.config.units

    # Set all statistic IDs to empty lists in result set to maintain the order
    if statistic_ids is not None:
        for stat_id in statistic_ids:
            result[stat_id] = []

    # Called in a tight loop so cache the function here
    _process_timestamp_to_utc_isoformat = process_timestamp_to_utc_isoformat

    # Append all statistic entries, and do unit conversion
    for meta_id, group in groupby(stats, lambda state: state.metadata_id):
        unit = metadata[meta_id]["unit_of_measurement"]
        statistic_id = metadata[meta_id]["statistic_id"]
        convert = UNIT_CONVERSIONS.get(unit, lambda x, units: x)
        ent_results = result[meta_id]
        ent_results.extend(
            {
                "statistic_id": statistic_id,
                "start": _process_timestamp_to_utc_isoformat(db_state.start),
                "mean": convert(db_state.mean, units),
                "min": convert(db_state.min, units),
                "max": convert(db_state.max, units),
                "last_reset": _process_timestamp_to_utc_isoformat(db_state.last_reset),
                "state": convert(db_state.state, units),
                "sum": convert(db_state.sum, units),
            }
            for db_state in group
        )

    # Filter out the empty lists if some states had 0 results.
    return {metadata[key]["statistic_id"]: val for key, val in result.items() if val}
