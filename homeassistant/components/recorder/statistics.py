"""Statistics helper."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import groupby
import logging
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import bindparam
from sqlalchemy.ext import baked
from sqlalchemy.orm.scoping import scoped_session

from homeassistant.const import PRESSURE_PA, TEMP_CELSIUS
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry
import homeassistant.util.dt as dt_util
import homeassistant.util.pressure as pressure_util
import homeassistant.util.temperature as temperature_util
from homeassistant.util.unit_system import UnitSystem

from .const import DOMAIN
from .models import (
    StatisticMetaData,
    Statistics,
    StatisticsMeta,
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


def async_setup(hass: HomeAssistant) -> None:
    """Set up the history hooks."""
    hass.data[STATISTICS_BAKERY] = baked.bakery()
    hass.data[STATISTICS_META_BAKERY] = baked.bakery()

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
    last_hour = dt_util.utcnow() - timedelta(hours=1)
    start = last_hour.replace(minute=0, second=0, microsecond=0)
    return start


def _get_metadata_ids(
    hass: HomeAssistant, session: scoped_session, statistic_ids: list[str]
) -> list[str]:
    """Resolve metadata_id for a list of statistic_ids."""
    baked_query = hass.data[STATISTICS_META_BAKERY](
        lambda session: session.query(*QUERY_STATISTIC_META)
    )
    baked_query += lambda q: q.filter(
        StatisticsMeta.statistic_id.in_(bindparam("statistic_ids"))
    )
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))

    return [id for id, _, _ in result] if result else []


def _get_or_add_metadata_id(
    hass: HomeAssistant,
    session: scoped_session,
    statistic_id: str,
    metadata: StatisticMetaData,
) -> str:
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
def compile_statistics(instance: Recorder, start: datetime) -> bool:
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


def _get_metadata(
    hass: HomeAssistant,
    session: scoped_session,
    statistic_ids: list[str] | None,
    statistic_type: str | None,
) -> dict[str, dict[str, str]]:
    """Fetch meta data."""

    def _meta(metas: list, wanted_metadata_id: str) -> dict[str, str] | None:
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
    elif statistic_type == "sum":
        baked_query += lambda q: q.filter(StatisticsMeta.has_sum.isnot(False))
    elif statistic_type is not None:
        return {}
    result = execute(baked_query(session).params(statistic_ids=statistic_ids))
    if not result:
        return {}

    metadata_ids = [metadata[0] for metadata in result]
    metadata = {}
    for _id in metadata_ids:
        meta = _meta(result, _id)
        if meta:
            metadata[_id] = meta
    return metadata


def _configured_unit(unit: str, units: UnitSystem) -> str:
    """Return the pressure and temperature units configured by the user."""
    if unit == PRESSURE_PA:
        return units.pressure_unit
    if unit == TEMP_CELSIUS:
        return units.temperature_unit
    return unit


def list_statistic_ids(
    hass: HomeAssistant, statistic_type: str | None = None
) -> list[dict[str, str] | None]:
    """Return statistic_ids and meta data."""
    units = hass.config.units
    statistic_ids = {}
    with session_scope(hass=hass) as session:
        metadata = _get_metadata(hass, session, None, statistic_type)

        for meta in metadata.values():
            unit = _configured_unit(meta["unit_of_measurement"], units)
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
            unit = _configured_unit(unit, units)
            platform_statistic_ids[statistic_id] = unit

        statistic_ids = {**statistic_ids, **platform_statistic_ids}

    return [
        {"statistic_id": _id, "unit_of_measurement": unit}
        for _id, unit in statistic_ids.items()
    ]


def statistics_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    statistic_ids: list[str] | None = None,
) -> dict[str, list[dict[str, str]]]:
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
        if not stats:
            return {}
        return _sorted_statistics_to_dict(hass, stats, statistic_ids, metadata)


def get_last_statistics(
    hass: HomeAssistant, number_of_stats: int, statistic_id: str
) -> dict[str, list[dict]]:
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
        if not stats:
            return {}

        return _sorted_statistics_to_dict(hass, stats, statistic_ids, metadata)


def _sorted_statistics_to_dict(
    hass: HomeAssistant,
    stats: list,
    statistic_ids: list[str] | None,
    metadata: dict[str, dict[str, str]],
) -> dict[str, list[dict]]:
    """Convert SQL results into JSON friendly data structure."""
    result: dict = defaultdict(list)
    units = hass.config.units

    # Set all statistic IDs to empty lists in result set to maintain the order
    if statistic_ids is not None:
        for stat_id in statistic_ids:
            result[stat_id] = []

    # Called in a tight loop so cache the function here
    _process_timestamp_to_utc_isoformat = process_timestamp_to_utc_isoformat

    # Append all statistic entries, and do unit conversion
    for meta_id, group in groupby(stats, lambda stat: stat.metadata_id):  # type: ignore
        unit = metadata[meta_id]["unit_of_measurement"]
        statistic_id = metadata[meta_id]["statistic_id"]
        convert: Callable[[Any, Any], float | None] = UNIT_CONVERSIONS.get(
            unit, lambda x, units: x  # type: ignore
        )
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
