"""Statistics helper for sensor."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
import datetime
import itertools
import logging
import math
from typing import Any

from sqlalchemy.orm.session import Session

from homeassistant.components.recorder import (
    DOMAIN as RECORDER_DOMAIN,
    get_instance,
    history,
    statistics,
)
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
    StatisticResult,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    REVOLUTIONS_PER_MINUTE,
    UnitOfIrradiance,
    UnitOfSoundPressure,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import entity_sources
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.loader import async_suggest_report_issue
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.enum import try_parse_enum
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    DOMAIN,
    SensorStateClass,
    UnitOfVolumeFlowRate,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class _StatisticsConfig:
    types: set[str]
    mean_type: StatisticMeanType = StatisticMeanType.NONE


DEFAULT_STATISTICS = {
    SensorStateClass.MEASUREMENT: _StatisticsConfig(
        {"mean", "min", "max"}, StatisticMeanType.ARITHMETIC
    ),
    SensorStateClass.MEASUREMENT_ANGLE: _StatisticsConfig(
        {"mean"}, StatisticMeanType.CIRCULAR
    ),
    SensorStateClass.TOTAL: _StatisticsConfig({"sum"}),
    SensorStateClass.TOTAL_INCREASING: _StatisticsConfig({"sum"}),
}

EQUIVALENT_UNITS = {
    "BTU/(h×ft²)": UnitOfIrradiance.BTUS_PER_HOUR_SQUARE_FOOT,
    "dBa": UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
    "RPM": REVOLUTIONS_PER_MINUTE,
    "ft3": UnitOfVolume.CUBIC_FEET,
    "m3": UnitOfVolume.CUBIC_METERS,
    "ft³/m": UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
}


# Keep track of entities for which a warning about decreasing value has been logged
SEEN_DIP: HassKey[set[str]] = HassKey(f"{DOMAIN}_seen_total_increasing_dip")
WARN_DIP: HassKey[set[str]] = HassKey(f"{DOMAIN}_warn_total_increasing_dip")
# Keep track of entities for which a warning about negative value has been logged
WARN_NEGATIVE: HassKey[set[str]] = HassKey(f"{DOMAIN}_warn_total_increasing_negative")
# Keep track of entities for which a warning about unsupported unit has been logged
WARN_UNSUPPORTED_UNIT: HassKey[set[str]] = HassKey(f"{DOMAIN}_warn_unsupported_unit")
WARN_UNSTABLE_UNIT: HassKey[set[str]] = HassKey(f"{DOMAIN}_warn_unstable_unit")
# Keep track of entities for which a warning about statistics mean algorithm change has been logged
WARN_STATISTICS_MEAN_CHANGED: HassKey[set[str]] = HassKey(
    f"{DOMAIN}_warn_statistics_mean_change"
)
# Link to dev statistics where issues around LTS can be fixed
LINK_DEV_STATISTICS = "https://my.home-assistant.io/redirect/developer_statistics"
STATE_CLASS_REMOVED_ISSUE = "state_class_removed"
UNITS_CHANGED_ISSUE = "units_changed"
MEAN_TYPE_CHANGED_ISSUE = "mean_type_changed"


def _get_sensor_states(hass: HomeAssistant) -> list[State]:
    """Get the current state of all sensors for which to compile statistics."""
    instance = get_instance(hass)
    # We check for state class first before calling the filter
    # function as the filter function is much more expensive
    # than checking the state class
    entity_filter = instance.entity_filter
    return [
        state
        for state in hass.states.all(DOMAIN)
        if (state_class := state.attributes.get(ATTR_STATE_CLASS))
        and (
            type(state_class) is SensorStateClass
            or try_parse_enum(SensorStateClass, state_class)
        )
        and (not entity_filter or entity_filter(state.entity_id))
    ]


def _time_weighted_arithmetic_mean(
    fstates: list[tuple[float, State]], start: datetime.datetime, end: datetime.datetime
) -> float:
    """Calculate a time weighted average.

    The average is calculated by weighting the states by duration in seconds between
    state changes.
    Note: there's no interpolation of values between state changes.
    """
    old_fstate: float | None = None
    old_start_time: datetime.datetime | None = None
    accumulated = 0.0

    for fstate, state in fstates:
        # The recorder will give us the last known state, which may be well
        # before the requested start time for the statistics
        start_time = max(state.last_updated, start)
        if old_start_time is None:
            # Adjust start time, if there was no last known state
            start = start_time
        else:
            duration = start_time - old_start_time
            # Accumulate the value, weighted by duration until next state change
            assert old_fstate is not None
            accumulated += old_fstate * duration.total_seconds()

        old_fstate = fstate
        old_start_time = start_time

    if old_fstate is not None:
        # Accumulate the value, weighted by duration until end of the period
        assert old_start_time is not None
        duration = end - old_start_time
        accumulated += old_fstate * duration.total_seconds()

    return accumulated / (end - start).total_seconds()


def _time_weighted_circular_mean(
    fstates: list[tuple[float, State]], start: datetime.datetime, end: datetime.datetime
) -> tuple[float, float]:
    """Calculate a time weighted circular mean.

    The circular mean is calculated by weighting the states by duration in seconds between
    state changes.
    Note: there's no interpolation of values between state changes.
    """
    old_fstate: float | None = None
    old_start_time: datetime.datetime | None = None
    values: list[tuple[float, float]] = []

    for fstate, state in fstates:
        # The recorder will give us the last known state, which may be well
        # before the requested start time for the statistics
        start_time = max(state.last_updated, start)
        if old_start_time is None:
            # Adjust start time, if there was no last known state
            start = start_time
        else:
            duration = (start_time - old_start_time).total_seconds()
            assert old_fstate is not None
            values.append((old_fstate, duration))

        old_fstate = fstate
        old_start_time = start_time

    if old_fstate is not None:
        # Add last value weighted by duration until end of the period
        assert old_start_time is not None
        duration = (end - old_start_time).total_seconds()
        values.append((old_fstate, duration))

    return statistics.weighted_circular_mean(values)


def _get_units(fstates: list[tuple[float, State]]) -> set[str | None]:
    """Return a set of all units."""
    return {item[1].attributes.get(ATTR_UNIT_OF_MEASUREMENT) for item in fstates}


def _equivalent_units(units: set[str | None]) -> bool:
    """Return True if the units are equivalent."""
    if len(units) == 1:
        return True
    units = {
        EQUIVALENT_UNITS[unit] if unit in EQUIVALENT_UNITS else unit  # noqa: SIM401
        for unit in units
    }
    return len(units) == 1


def _entity_history_to_float_and_state(
    entity_history: Iterable[State],
) -> list[tuple[float, State]]:
    """Return a list of (float, state) tuples for the given entity."""
    float_states: list[tuple[float, State]] = []
    append = float_states.append
    isfinite = math.isfinite
    for state in entity_history:
        try:
            if (float_state := float(state.state)) is not None and isfinite(
                float_state
            ):
                append((float_state, state))
        except (ValueError, TypeError):
            pass
    return float_states


def _is_numeric(state: State) -> bool:
    """Return if the state is numeric."""
    with suppress(ValueError, TypeError):
        if (num_state := float(state.state)) is not None and math.isfinite(num_state):
            return True
    return False


def _normalize_states(
    hass: HomeAssistant,
    old_metadatas: dict[str, tuple[int, StatisticMetaData]],
    fstates: list[tuple[float, State]],
    entity_id: str,
) -> tuple[str | None, list[tuple[float, State]]]:
    """Normalize units."""
    state_unit: str | None = None
    statistics_unit: str | None
    state_unit = fstates[0][1].attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    old_metadata = old_metadatas[entity_id][1] if entity_id in old_metadatas else None
    if not old_metadata:
        # We've not seen this sensor before, the first valid state determines the unit
        # used for statistics
        statistics_unit = state_unit
    else:
        # We have seen this sensor before, use the unit from metadata
        statistics_unit = old_metadata["unit_of_measurement"]

    if statistics_unit not in statistics.STATISTIC_UNIT_TO_UNIT_CONVERTER:
        # The unit used by this sensor doesn't support unit conversion

        all_units = _get_units(fstates)
        if not _equivalent_units(all_units):
            if WARN_UNSTABLE_UNIT not in hass.data:
                hass.data[WARN_UNSTABLE_UNIT] = set()
            if entity_id not in hass.data[WARN_UNSTABLE_UNIT]:
                hass.data[WARN_UNSTABLE_UNIT].add(entity_id)
                extra = ""
                if old_metadata:
                    extra = (
                        " and matches the unit of already compiled statistics "
                        f"({old_metadata['unit_of_measurement']})"
                    )
                _LOGGER.warning(
                    (
                        "The unit of %s is changing, got multiple %s, generation of"
                        " long term statistics will be suppressed unless the unit is"
                        " stable%s. Go to %s to fix this"
                    ),
                    entity_id,
                    all_units,
                    extra,
                    LINK_DEV_STATISTICS,
                )
            return None, []

        return state_unit, fstates

    converter = statistics.STATISTIC_UNIT_TO_UNIT_CONVERTER[statistics_unit]
    valid_fstates: list[tuple[float, State]] = []
    convert: Callable[[float], float] | None = None
    last_unit: str | None | UndefinedType = UNDEFINED
    valid_units = converter.VALID_UNITS

    for fstate, state in fstates:
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        # Exclude states with unsupported unit from statistics
        if state_unit not in valid_units:
            if WARN_UNSUPPORTED_UNIT not in hass.data:
                hass.data[WARN_UNSUPPORTED_UNIT] = set()
            if entity_id not in hass.data[WARN_UNSUPPORTED_UNIT]:
                hass.data[WARN_UNSUPPORTED_UNIT].add(entity_id)
                _LOGGER.warning(
                    (
                        "The unit of %s (%s) cannot be converted to the unit of"
                        " previously compiled statistics (%s). Generation of long term"
                        " statistics will be suppressed unless the unit changes back to"
                        " %s or a compatible unit. Go to %s to fix this"
                    ),
                    entity_id,
                    state_unit,
                    statistics_unit,
                    statistics_unit,
                    LINK_DEV_STATISTICS,
                )
            continue

        if state_unit != last_unit:
            # The unit of measurement has changed since the last state change
            # recreate the converter factory
            if state_unit == statistics_unit:
                convert = None
            else:
                convert = converter.converter_factory(state_unit, statistics_unit)
            last_unit = state_unit

        if convert is not None:
            fstate = convert(fstate)

        valid_fstates.append((fstate, state))

    return statistics_unit, valid_fstates


def _suggest_report_issue(hass: HomeAssistant, entity_id: str) -> str:
    """Suggest to report an issue."""
    entity_info = entity_sources(hass).get(entity_id)

    return async_suggest_report_issue(
        hass, integration_domain=entity_info["domain"] if entity_info else None
    )


def warn_dip(
    hass: HomeAssistant, entity_id: str, state: State, previous_fstate: float
) -> None:
    """Log a warning once if a sensor with state_class_total has a decreasing value.

    The log will be suppressed until two dips have been seen to prevent warning due to
    rounding issues with databases storing the state as a single precision float, which
    was fixed in recorder DB version 20.
    """
    if SEEN_DIP not in hass.data:
        hass.data[SEEN_DIP] = set()
    if entity_id not in hass.data[SEEN_DIP]:
        hass.data[SEEN_DIP].add(entity_id)
        return
    if WARN_DIP not in hass.data:
        hass.data[WARN_DIP] = set()
    if entity_id not in hass.data[WARN_DIP]:
        hass.data[WARN_DIP].add(entity_id)
        entity_info = entity_sources(hass).get(entity_id)
        domain = entity_info["domain"] if entity_info else None
        if domain in ["energy", "growatt_server", "solaredge"]:
            return
        _LOGGER.warning(
            (
                "Entity %s %shas state class total_increasing, but its state is not"
                " strictly increasing. Triggered by state %s (%s) with last_updated set"
                " to %s. Please %s"
            ),
            entity_id,
            f"from integration {domain} " if domain else "",
            state.state,
            previous_fstate,
            state.last_updated.isoformat(),
            _suggest_report_issue(hass, entity_id),
        )


def warn_negative(hass: HomeAssistant, entity_id: str, state: State) -> None:
    """Log a warning once if a sensor with state_class_total has a negative value."""
    if WARN_NEGATIVE not in hass.data:
        hass.data[WARN_NEGATIVE] = set()
    if entity_id not in hass.data[WARN_NEGATIVE]:
        hass.data[WARN_NEGATIVE].add(entity_id)
        entity_info = entity_sources(hass).get(entity_id)
        domain = entity_info["domain"] if entity_info else None
        _LOGGER.warning(
            (
                "Entity %s %shas state class total_increasing, but its state is "
                "negative. Triggered by state %s with last_updated set to %s. Please %s"
            ),
            entity_id,
            f"from integration {domain} " if domain else "",
            state.state,
            state.last_updated.isoformat(),
            _suggest_report_issue(hass, entity_id),
        )


def reset_detected(
    hass: HomeAssistant,
    entity_id: str,
    fstate: float,
    previous_fstate: float | None,
    state: State,
) -> bool:
    """Test if a total_increasing sensor has been reset."""
    if previous_fstate is None:
        return False

    if 0.9 * previous_fstate <= fstate < previous_fstate:
        warn_dip(hass, entity_id, state, previous_fstate)

    if fstate < 0:
        warn_negative(hass, entity_id, state)
        raise HomeAssistantError

    return fstate < 0.9 * previous_fstate


def _wanted_statistics(sensor_states: list[State]) -> dict[str, _StatisticsConfig]:
    """Prepare a dict with wanted statistics for entities."""
    return {
        state.entity_id: DEFAULT_STATISTICS[state.attributes[ATTR_STATE_CLASS]]
        for state in sensor_states
    }


def _last_reset_as_utc_isoformat(last_reset_s: Any, entity_id: str) -> str | None:
    """Parse last_reset and convert it to UTC."""
    if last_reset_s is None:
        return None
    if isinstance(last_reset_s, str):
        last_reset = dt_util.parse_datetime(last_reset_s)
    else:
        last_reset = None
    if last_reset is None:
        _LOGGER.warning(
            "Ignoring invalid last reset '%s' for %s", last_reset_s, entity_id
        )
        return None
    return dt_util.as_utc(last_reset).isoformat()


def _timestamp_to_isoformat_or_none(timestamp: float | None) -> str | None:
    """Convert a timestamp to ISO format or return None."""
    if timestamp is None:
        return None
    return dt_util.utc_from_timestamp(timestamp).isoformat()


def compile_statistics(  # noqa: C901
    hass: HomeAssistant,
    session: Session,
    start: datetime.datetime,
    end: datetime.datetime,
) -> statistics.PlatformCompiledStatistics:
    """Compile statistics for all entities during start-end."""
    result: list[StatisticResult] = []

    sensor_states = _get_sensor_states(hass)
    wanted_statistics = _wanted_statistics(sensor_states)
    # Get history between start and end
    entities_full_history = [
        i.entity_id
        for i in sensor_states
        if "sum" in wanted_statistics[i.entity_id].types
    ]
    history_list: dict[str, list[State]] = {}
    if entities_full_history:
        history_list = history.get_full_significant_states_with_session(
            hass,
            session,
            start - datetime.timedelta.resolution,
            end,
            entity_ids=entities_full_history,
            significant_changes_only=False,
        )
    entities_significant_history = [
        i.entity_id
        for i in sensor_states
        if "sum" not in wanted_statistics[i.entity_id].types
    ]
    if entities_significant_history:
        _history_list = history.get_full_significant_states_with_session(
            hass,
            session,
            start - datetime.timedelta.resolution,
            end,
            entity_ids=entities_significant_history,
        )
        history_list = {**history_list, **_history_list}

    entities_with_float_states: dict[str, list[tuple[float, State]]] = {}
    for _state in sensor_states:
        entity_id = _state.entity_id
        # If there are no recent state changes, the sensor's state may already be pruned
        # from the recorder. Get the state from the state machine instead.
        try:
            entity_history = history_list[entity_id]
        except KeyError:
            entity_history = [_state] if _state.last_changed < end else []
        if not entity_history:
            continue
        if not (float_states := _entity_history_to_float_and_state(entity_history)):
            continue
        entities_with_float_states[entity_id] = float_states

    # Only lookup metadata for entities that have valid float states
    # since it will result in cache misses for statistic_ids
    # that are not in the metadata table and we are not working
    # with them anyway.
    old_metadatas = statistics.get_metadata_with_session(
        get_instance(hass), session, statistic_ids=set(entities_with_float_states)
    )
    to_process: list[tuple[str, str | None, str, list[tuple[float, State]]]] = []
    to_query: set[str] = set()
    for _state in sensor_states:
        entity_id = _state.entity_id
        if not (maybe_float_states := entities_with_float_states.get(entity_id)):
            continue
        statistics_unit, valid_float_states = _normalize_states(
            hass,
            old_metadatas,
            maybe_float_states,
            entity_id,
        )
        if not valid_float_states:
            continue
        state_class: str = _state.attributes[ATTR_STATE_CLASS]
        to_process.append((entity_id, statistics_unit, state_class, valid_float_states))
        if "sum" in wanted_statistics[entity_id].types:
            to_query.add(entity_id)

    last_stats = statistics.get_latest_short_term_statistics_with_session(
        hass, session, to_query, {"last_reset", "state", "sum"}, metadata=old_metadatas
    )
    for (  # pylint: disable=too-many-nested-blocks
        entity_id,
        statistics_unit,
        state_class,
        valid_float_states,
    ) in to_process:
        mean_type = StatisticMeanType.NONE
        if "mean" in wanted_statistics[entity_id].types:
            mean_type = wanted_statistics[entity_id].mean_type

        # Check metadata
        if old_metadata := old_metadatas.get(entity_id):
            if not _equivalent_units(
                {old_metadata[1]["unit_of_measurement"], statistics_unit}
            ):
                if WARN_UNSTABLE_UNIT not in hass.data:
                    hass.data[WARN_UNSTABLE_UNIT] = set()
                if entity_id not in hass.data[WARN_UNSTABLE_UNIT]:
                    hass.data[WARN_UNSTABLE_UNIT].add(entity_id)
                    _LOGGER.warning(
                        (
                            "The unit of %s (%s) cannot be converted to the unit of"
                            " previously compiled statistics (%s). Generation of long"
                            " term statistics will be suppressed unless the unit"
                            " changes back to %s or a compatible unit. Go to %s to fix"
                            " this"
                        ),
                        entity_id,
                        statistics_unit,
                        old_metadata[1]["unit_of_measurement"],
                        old_metadata[1]["unit_of_measurement"],
                        LINK_DEV_STATISTICS,
                    )
                continue

            if (
                mean_type is not StatisticMeanType.NONE
                and (old_mean_type := old_metadata[1]["mean_type"])
                is not StatisticMeanType.NONE
                and mean_type != old_mean_type
            ):
                if WARN_STATISTICS_MEAN_CHANGED not in hass.data:
                    hass.data[WARN_STATISTICS_MEAN_CHANGED] = set()
                if entity_id not in hass.data[WARN_STATISTICS_MEAN_CHANGED]:
                    hass.data[WARN_STATISTICS_MEAN_CHANGED].add(entity_id)
                    _LOGGER.warning(
                        (
                            "The statistics mean algorithm for %s have changed from %s to %s."
                            " Generation of long term statistics will be suppressed"
                            " unless it changes back or go to %s to delete the old"
                            " statistics"
                        ),
                        entity_id,
                        old_mean_type.name,
                        mean_type.name,
                        LINK_DEV_STATISTICS,
                    )
                continue

        # Set meta data
        meta: StatisticMetaData = {
            "mean_type": mean_type,
            "has_sum": "sum" in wanted_statistics[entity_id].types,
            "name": None,
            "source": RECORDER_DOMAIN,
            "statistic_id": entity_id,
            "unit_of_measurement": statistics_unit,
        }

        # Make calculations
        stat: StatisticData = {"start": start}
        if "max" in wanted_statistics[entity_id].types:
            stat["max"] = max(
                *itertools.islice(zip(*valid_float_states, strict=False), 1)
            )
        if "min" in wanted_statistics[entity_id].types:
            stat["min"] = min(
                *itertools.islice(zip(*valid_float_states, strict=False), 1)
            )

        match mean_type:
            case StatisticMeanType.ARITHMETIC:
                stat["mean"] = _time_weighted_arithmetic_mean(
                    valid_float_states, start, end
                )
            case StatisticMeanType.CIRCULAR:
                stat["mean"], stat["mean_weight"] = _time_weighted_circular_mean(
                    valid_float_states, start, end
                )

        if "sum" in wanted_statistics[entity_id].types:
            last_reset = old_last_reset = None
            new_state = old_state = None
            _sum = 0.0
            if entity_id in last_stats:
                # We have compiled history for this sensor before,
                # use that as a starting point.
                last_stat = last_stats[entity_id][0]
                last_reset = _timestamp_to_isoformat_or_none(last_stat["last_reset"])
                old_last_reset = last_reset
                # If there are no previous values and has_sum
                # was previously false there will be no last_stat
                # for state or sum
                new_state = old_state = last_stat.get("state")
                _sum = last_stat.get("sum") or 0.0

            for fstate, state in valid_float_states:
                reset = False
                if (
                    state_class != SensorStateClass.TOTAL_INCREASING
                    and (
                        last_reset := _last_reset_as_utc_isoformat(
                            state.attributes.get("last_reset"), entity_id
                        )
                    )
                    != old_last_reset
                    and last_reset is not None
                ):
                    if old_state is None:
                        _LOGGER.info(
                            (
                                "Compiling initial sum statistics for %s, zero point"
                                " set to %s"
                            ),
                            entity_id,
                            fstate,
                        )
                    else:
                        _LOGGER.info(
                            (
                                "Detected new cycle for %s, last_reset set to %s (old"
                                " last_reset %s)"
                            ),
                            entity_id,
                            last_reset,
                            old_last_reset,
                        )
                    reset = True
                elif old_state is None and last_reset is None:
                    reset = True
                    _LOGGER.info(
                        "Compiling initial sum statistics for %s, zero point set to %s",
                        entity_id,
                        fstate,
                    )
                elif state_class == SensorStateClass.TOTAL_INCREASING:
                    try:
                        if old_state is None or reset_detected(
                            hass, entity_id, fstate, new_state, state
                        ):
                            reset = True
                            _LOGGER.info(
                                (
                                    "Detected new cycle for %s, value dropped from %s"
                                    " to %s, triggered by state with last_updated set"
                                    " to %s"
                                ),
                                entity_id,
                                new_state,
                                fstate,
                                state.last_updated.isoformat(),
                            )
                    except HomeAssistantError:
                        continue

                if reset:
                    # The sensor has been reset, update the sum
                    if old_state is not None and new_state is not None:
                        _sum += new_state - old_state
                    # ..and update the starting point
                    new_state = fstate
                    old_last_reset = last_reset
                    # Force a new cycle for an existing sensor to start at 0
                    if old_state is not None:
                        old_state = 0.0
                    else:
                        old_state = new_state
                else:
                    new_state = fstate

            if new_state is None or old_state is None:
                # No valid updates
                continue

            # Update the sum with the last state
            _sum += new_state - old_state
            if last_reset is not None:
                stat["last_reset"] = dt_util.parse_datetime(last_reset)
            stat["sum"] = _sum
            stat["state"] = new_state

        result.append({"meta": meta, "stat": stat})

    return statistics.PlatformCompiledStatistics(result, old_metadatas)


def list_statistic_ids(
    hass: HomeAssistant,
    statistic_ids: list[str] | tuple[str] | None = None,
    statistic_type: str | None = None,
) -> dict:
    """Return all or filtered statistic_ids and meta data."""
    entities = _get_sensor_states(hass)

    result: dict[str, StatisticMetaData] = {}

    for state in entities:
        entity_id = state.entity_id
        if statistic_ids is not None and entity_id not in statistic_ids:
            continue

        attributes = state.attributes
        state_class = attributes[ATTR_STATE_CLASS]
        provided_statistics = DEFAULT_STATISTICS[state_class]
        if (
            statistic_type is not None
            and statistic_type not in provided_statistics.types
        ):
            continue

        if (
            (has_sum := "sum" in provided_statistics.types)
            and ATTR_LAST_RESET not in attributes
            and state_class == SensorStateClass.MEASUREMENT
        ):
            continue

        mean_type = StatisticMeanType.NONE
        if "mean" in provided_statistics.types:
            mean_type = provided_statistics.mean_type

        result[entity_id] = {
            "mean_type": mean_type,
            "has_sum": has_sum,
            "name": None,
            "source": RECORDER_DOMAIN,
            "statistic_id": entity_id,
            "unit_of_measurement": attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        }

    return result


@callback
def _update_issues(
    report_issue: Callable[[str, str, dict[str, Any]], None],
    sensor_states: list[State],
    metadatas: dict[str, tuple[int, StatisticMetaData]],
) -> None:
    """Update repair issues."""
    for state in sensor_states:
        entity_id = state.entity_id
        numeric = _is_numeric(state)
        state_class = try_parse_enum(
            SensorStateClass, state.attributes.get(ATTR_STATE_CLASS)
        )
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if metadata := metadatas.get(entity_id):
            if numeric and state_class is None:
                # Sensor no longer has a valid state class
                report_issue(
                    STATE_CLASS_REMOVED_ISSUE,
                    entity_id,
                    {"statistic_id": entity_id},
                )

            metadata_unit = metadata[1]["unit_of_measurement"]
            converter = statistics.STATISTIC_UNIT_TO_UNIT_CONVERTER.get(metadata_unit)
            if not converter:
                if numeric and not _equivalent_units({state_unit, metadata_unit}):
                    # The unit has changed, and it's not possible to convert
                    report_issue(
                        UNITS_CHANGED_ISSUE,
                        entity_id,
                        {
                            "statistic_id": entity_id,
                            "state_unit": state_unit,
                            "metadata_unit": metadata_unit,
                            "supported_unit": metadata_unit,
                        },
                    )
            elif numeric and state_unit not in converter.VALID_UNITS:
                # The state unit can't be converted to the unit in metadata
                valid_units = (unit or "<None>" for unit in converter.VALID_UNITS)
                valid_units_str = ", ".join(sorted(valid_units))
                report_issue(
                    UNITS_CHANGED_ISSUE,
                    entity_id,
                    {
                        "statistic_id": entity_id,
                        "state_unit": state_unit,
                        "metadata_unit": metadata_unit,
                        "supported_unit": valid_units_str,
                    },
                )

            if (
                (metadata_mean_type := metadata[1]["mean_type"]) is not None
                and state_class
                and (state_mean_type := DEFAULT_STATISTICS[state_class].mean_type)
                != metadata_mean_type
            ):
                # The mean type has changed and the old statistics are not valid anymore
                report_issue(
                    MEAN_TYPE_CHANGED_ISSUE,
                    entity_id,
                    {
                        "statistic_id": entity_id,
                        "metadata_mean_type": metadata_mean_type,
                        "state_mean_type": state_mean_type,
                    },
                )


def update_statistics_issues(
    hass: HomeAssistant,
    session: Session,
) -> None:
    """Validate statistics."""
    instance = get_instance(hass)
    sensor_states = hass.states.all(DOMAIN)
    metadatas = statistics.get_metadata_with_session(
        instance, session, statistic_source=RECORDER_DOMAIN
    )

    @callback
    def get_sensor_statistics_issues(hass: HomeAssistant) -> set[str]:
        """Return a list of statistics issues."""
        issues = set()
        issue_registry = ir.async_get(hass)
        for issue in issue_registry.issues.values():
            if (
                issue.domain != DOMAIN
                or not (issue_data := issue.data)
                or issue_data.get("issue_type")
                not in (
                    STATE_CLASS_REMOVED_ISSUE,
                    UNITS_CHANGED_ISSUE,
                    MEAN_TYPE_CHANGED_ISSUE,
                )
            ):
                continue
            issues.add(issue.issue_id)
        return issues

    issues = run_callback_threadsafe(
        hass.loop, get_sensor_statistics_issues, hass
    ).result()

    def create_issue_registry_issue(
        issue_type: str, statistic_id: str, data: dict[str, Any]
    ) -> None:
        """Create an issue registry issue."""
        issue_id = f"{issue_type}_{statistic_id}"
        issues.discard(issue_id)
        ir.create_issue(
            hass,
            DOMAIN,
            issue_id,
            data=data | {"issue_type": issue_type},
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=issue_type,
            translation_placeholders=data,
        )

    _update_issues(
        create_issue_registry_issue,
        sensor_states,
        metadatas,
    )
    for issue_id in issues:
        hass.loop.call_soon_threadsafe(ir.async_delete_issue, hass, DOMAIN, issue_id)


def validate_statistics(
    hass: HomeAssistant,
) -> dict[str, list[statistics.ValidationIssue]]:
    """Validate statistics."""
    validation_result = defaultdict(list)

    sensor_states = hass.states.all(DOMAIN)
    metadatas = statistics.get_metadata(hass, statistic_source=RECORDER_DOMAIN)
    sensor_entity_ids = {i.entity_id for i in sensor_states}
    sensor_statistic_ids = set(metadatas)
    instance = get_instance(hass)
    entity_filter = instance.entity_filter

    def create_statistic_validation_issue(
        issue_type: str, statistic_id: str, data: dict[str, Any]
    ) -> None:
        """Create a statistic validation issue."""
        validation_result[statistic_id].append(
            statistics.ValidationIssue(issue_type, data)
        )

    _update_issues(
        create_statistic_validation_issue,
        sensor_states,
        metadatas,
    )

    for state in sensor_states:
        entity_id = state.entity_id
        state_class = try_parse_enum(
            SensorStateClass, state.attributes.get(ATTR_STATE_CLASS)
        )

        if entity_id in metadatas:
            if entity_filter and not entity_filter(state.entity_id):
                # Sensor was previously recorded, but no longer is
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "entity_no_longer_recorded",
                        {"statistic_id": entity_id},
                    )
                )
        elif state_class is not None:
            if entity_filter and not entity_filter(state.entity_id):
                # Sensor is not recorded
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "entity_not_recorded",
                        {"statistic_id": entity_id},
                    )
                )

    for statistic_id in sensor_statistic_ids - sensor_entity_ids:
        if split_entity_id(statistic_id)[0] != DOMAIN:
            continue
        # There is no sensor matching the statistics_id
        validation_result[statistic_id].append(
            statistics.ValidationIssue(
                "no_state",
                {
                    "statistic_id": statistic_id,
                },
            )
        )

    return validation_result
