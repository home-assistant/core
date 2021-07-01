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
    Statistics.statistic_id,
    Statistics.start,
    Statistics.mean,
    Statistics.min,
    Statistics.max,
    Statistics.last_reset,
    Statistics.state,
    Statistics.sum,
]

QUERY_STATISTIC_IDS = [
    Statistics.statistic_id,
]

QUERY_STATISTIC_META = [
    StatisticsMeta.statistic_id,
    StatisticsMeta.unit_of_measurement,
]

STATISTICS_BAKERY = "recorder_statistics_bakery"
STATISTICS_META_BAKERY = "recorder_statistics_bakery"

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


@retryable_database_job("statistics")
def compile_statistics(instance: Recorder, start: datetime.datetime) -> bool:
    """Compile statistics."""
    start = dt_util.as_utc(start)
    end = start + timedelta(hours=1)
    _LOGGER.debug(
        "Compiling statistics for %s-%s",
        start,
        end,
    )
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
                session.add(
                    Statistics.from_stats(DOMAIN, entity_id, start, stat["stat"])
                )
                exists = session.query(
                    session.query(StatisticsMeta)
                    .filter_by(statistic_id=entity_id)
                    .exists()
                ).scalar()
                if not exists:
                    unit = stat["meta"]["unit_of_measurement"]
                    session.add(StatisticsMeta.from_meta(DOMAIN, entity_id, unit))

    return True


def _get_meta_data(hass, session, statistic_ids):
    """Fetch meta data."""

    def _meta(metas, wanted_statistic_id):
        meta = {"statistic_id": wanted_statistic_id, "unit_of_measurement": None}
        for statistic_id, unit in metas:
            if statistic_id == wanted_statistic_id:
                meta["unit_of_measurement"] = unit
        return meta

    baked_query = hass.data[STATISTICS_META_BAKERY](
        lambda session: session.query(*QUERY_STATISTIC_META)
    )
    if statistic_ids is not None:
        baked_query += lambda q: q.filter(
            StatisticsMeta.statistic_id.in_(bindparam("statistic_ids"))
        )

    result = execute(baked_query(session).params(statistic_ids=statistic_ids))

    if statistic_ids is None:
        statistic_ids = [statistic_id[0] for statistic_id in result]

    return {id: _meta(result, id) for id in statistic_ids}


def _unit_system_unit(unit: str, units) -> str:
    if unit == PRESSURE_PA:
        return units.pressure_unit
    if unit == TEMP_CELSIUS:
        return units.temperature_unit
    return unit


def list_statistic_ids(hass, statistic_type=None):
    """Return statistic_ids."""
    units = hass.config.units
    with session_scope(hass=hass) as session:
        baked_query = hass.data[STATISTICS_BAKERY](
            lambda session: session.query(*QUERY_STATISTIC_IDS).distinct()
        )

        if statistic_type == "mean":
            baked_query += lambda q: q.filter(Statistics.mean.isnot(None))
        if statistic_type == "sum":
            baked_query += lambda q: q.filter(Statistics.sum.isnot(None))

        baked_query += lambda q: q.order_by(Statistics.statistic_id)

        result = execute(baked_query(session))
        statistic_ids_list = [statistic_id[0] for statistic_id in result]
        statistic_ids = _get_meta_data(hass, session, statistic_ids_list)
        for statistic_id in statistic_ids.values():
            unit = _unit_system_unit(statistic_id["unit_of_measurement"], units)
            statistic_id["unit_of_measurement"] = unit

        return list(statistic_ids.values())


def statistics_during_period(hass, start_time, end_time=None, statistic_ids=None):
    """Return states changes during UTC period start_time - end_time."""
    with session_scope(hass=hass) as session:
        baked_query = hass.data[STATISTICS_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS)
        )

        baked_query += lambda q: q.filter(Statistics.start >= bindparam("start_time"))

        if end_time is not None:
            baked_query += lambda q: q.filter(Statistics.start < bindparam("end_time"))

        if statistic_ids is not None:
            baked_query += lambda q: q.filter(
                Statistics.statistic_id.in_(bindparam("statistic_ids"))
            )
            statistic_ids = [statistic_id.lower() for statistic_id in statistic_ids]

        baked_query += lambda q: q.order_by(Statistics.statistic_id, Statistics.start)

        stats = execute(
            baked_query(session).params(
                start_time=start_time, end_time=end_time, statistic_ids=statistic_ids
            )
        )
        meta_data = _get_meta_data(hass, session, statistic_ids)
        return _sorted_statistics_to_dict(hass, stats, statistic_ids, meta_data)


def get_last_statistics(hass, number_of_stats, statistic_id=None):
    """Return the last number_of_stats statistics."""
    with session_scope(hass=hass) as session:
        baked_query = hass.data[STATISTICS_BAKERY](
            lambda session: session.query(*QUERY_STATISTICS)
        )

        if statistic_id is not None:
            baked_query += lambda q: q.filter_by(statistic_id=bindparam("statistic_id"))

        baked_query += lambda q: q.order_by(
            Statistics.statistic_id, Statistics.start.desc()
        )

        baked_query += lambda q: q.limit(bindparam("number_of_stats"))

        stats = execute(
            baked_query(session).params(
                number_of_stats=number_of_stats, statistic_id=statistic_id
            )
        )

        statistic_ids = [statistic_id] if statistic_id is not None else None
        meta_data = _get_meta_data(hass, session, statistic_ids)
        return _sorted_statistics_to_dict(hass, stats, statistic_ids, meta_data)


def _sorted_statistics_to_dict(
    hass,
    stats,
    statistic_ids,
    meta_data,
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
    for ent_id, group in groupby(stats, lambda state: state.statistic_id):
        unit = meta_data[ent_id]["unit_of_measurement"]
        convert = UNIT_CONVERSIONS.get(unit, lambda x, units: x)
        ent_results = result[ent_id]
        ent_results.extend(
            {
                "statistic_id": db_state.statistic_id,
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
    return {key: val for key, val in result.items() if val}
