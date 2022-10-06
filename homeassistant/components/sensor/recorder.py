"""Statistics helper for sensor."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, MutableMapping
import datetime
import itertools
import logging
import math
from typing import Any

from sqlalchemy.orm.session import Session

from homeassistant.components.recorder import (
    DOMAIN as RECORDER_DOMAIN,
    history,
    is_entity_recorded,
    statistics,
    util as recorder_util,
)
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
    StatisticResult,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import entity_sources
from homeassistant.util import dt as dt_util

from . import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    STATE_CLASSES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_STATISTICS = {
    STATE_CLASS_MEASUREMENT: {"mean", "min", "max"},
    STATE_CLASS_TOTAL: {"sum"},
    STATE_CLASS_TOTAL_INCREASING: {"sum"},
}

# Keep track of entities for which a warning about decreasing value has been logged
SEEN_DIP = "sensor_seen_total_increasing_dip"
WARN_DIP = "sensor_warn_total_increasing_dip"
# Keep track of entities for which a warning about negative value has been logged
WARN_NEGATIVE = "sensor_warn_total_increasing_negative"
# Keep track of entities for which a warning about unsupported unit has been logged
WARN_UNSUPPORTED_UNIT = "sensor_warn_unsupported_unit"
WARN_UNSTABLE_UNIT = "sensor_warn_unstable_unit"
# Link to dev statistics where issues around LTS can be fixed
LINK_DEV_STATISTICS = "https://my.home-assistant.io/redirect/developer_statistics"


def _get_sensor_states(hass: HomeAssistant) -> list[State]:
    """Get the current state of all sensors for which to compile statistics."""
    all_sensors = hass.states.all(DOMAIN)
    statistics_sensors = []

    for state in all_sensors:
        if not is_entity_recorded(hass, state.entity_id):
            continue
        if (state.attributes.get(ATTR_STATE_CLASS)) not in STATE_CLASSES:
            continue
        statistics_sensors.append(state)

    return statistics_sensors


def _time_weighted_average(
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
        start_time = start if state.last_updated < start else state.last_updated
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


def _get_units(fstates: list[tuple[float, State]]) -> set[str | None]:
    """Return True if all states have the same unit."""
    return {item[1].attributes.get(ATTR_UNIT_OF_MEASUREMENT) for item in fstates}


def _parse_float(state: str) -> float:
    """Parse a float string, throw on inf or nan."""
    fstate = float(state)
    if math.isnan(fstate) or math.isinf(fstate):
        raise ValueError
    return fstate


def _normalize_states(
    hass: HomeAssistant,
    session: Session,
    old_metadatas: dict[str, tuple[int, StatisticMetaData]],
    entity_history: Iterable[State],
    entity_id: str,
) -> tuple[str | None, str | None, list[tuple[float, State]]]:
    """Normalize units."""
    old_metadata = old_metadatas[entity_id][1] if entity_id in old_metadatas else None
    state_unit: str | None = None

    fstates: list[tuple[float, State]] = []
    for state in entity_history:
        try:
            fstate = _parse_float(state.state)
        except (ValueError, TypeError):  # TypeError to guard for NULL state in DB
            continue
        fstates.append((fstate, state))

    if not fstates:
        return None, None, fstates

    state_unit = fstates[0][1].attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    statistics_unit: str | None
    if not old_metadata:
        # We've not seen this sensor before, the first valid state determines the unit
        # used for statistics
        statistics_unit = state_unit
    else:
        # We have seen this sensor before, use the unit from metadata
        statistics_unit = old_metadata["unit_of_measurement"]

    if (
        not statistics_unit
        or statistics_unit not in statistics.STATISTIC_UNIT_TO_UNIT_CONVERTER
    ):
        # The unit used by this sensor doesn't support unit conversion

        all_units = _get_units(fstates)
        if len(all_units) > 1:
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
                    "The unit of %s is changing, got multiple %s, generation of long term "
                    "statistics will be suppressed unless the unit is stable%s. "
                    "Go to %s to fix this",
                    entity_id,
                    all_units,
                    extra,
                    LINK_DEV_STATISTICS,
                )
            return None, None, []
        state_unit = fstates[0][1].attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        return state_unit, state_unit, fstates

    converter = statistics.STATISTIC_UNIT_TO_UNIT_CONVERTER[statistics_unit]
    valid_fstates: list[tuple[float, State]] = []

    for fstate, state in fstates:
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        # Exclude states with unsupported unit from statistics
        if state_unit not in converter.VALID_UNITS:
            if WARN_UNSUPPORTED_UNIT not in hass.data:
                hass.data[WARN_UNSUPPORTED_UNIT] = set()
            if entity_id not in hass.data[WARN_UNSUPPORTED_UNIT]:
                hass.data[WARN_UNSUPPORTED_UNIT].add(entity_id)
                _LOGGER.warning(
                    "The unit of %s (%s) can not be converted to the unit of previously "
                    "compiled statistics (%s). Generation of long term statistics "
                    "will be suppressed unless the unit changes back to %s or a "
                    "compatible unit. "
                    "Go to %s to fix this",
                    entity_id,
                    state_unit,
                    statistics_unit,
                    statistics_unit,
                    LINK_DEV_STATISTICS,
                )
            continue

        valid_fstates.append(
            (
                converter.convert(
                    fstate, from_unit=state_unit, to_unit=statistics_unit
                ),
                state,
            )
        )

    return statistics_unit, state_unit, valid_fstates


def _suggest_report_issue(hass: HomeAssistant, entity_id: str) -> str:
    """Suggest to report an issue."""
    domain = entity_sources(hass).get(entity_id, {}).get("domain")
    custom_component = entity_sources(hass).get(entity_id, {}).get("custom_component")
    report_issue = ""
    if custom_component:
        report_issue = "report it to the custom integration author."
    else:
        report_issue = (
            "create a bug report at "
            "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
        )
        if domain:
            report_issue += f"+label%3A%22integration%3A+{domain}%22"

    return report_issue


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
        domain = entity_sources(hass).get(entity_id, {}).get("domain")
        if domain in ["energy", "growatt_server", "solaredge"]:
            return
        _LOGGER.warning(
            "Entity %s %shas state class total_increasing, but its state is "
            "not strictly increasing. Triggered by state %s (%s) with last_updated set to %s. "
            "Please %s",
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
        domain = entity_sources(hass).get(entity_id, {}).get("domain")
        _LOGGER.warning(
            "Entity %s %shas state class total_increasing, but its state is "
            "negative. Triggered by state %s with last_updated set to %s. Please %s",
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


def _wanted_statistics(sensor_states: list[State]) -> dict[str, set[str]]:
    """Prepare a dict with wanted statistics for entities."""
    wanted_statistics = {}
    for state in sensor_states:
        state_class = state.attributes[ATTR_STATE_CLASS]
        wanted_statistics[state.entity_id] = DEFAULT_STATISTICS[state_class]
    return wanted_statistics


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


def compile_statistics(
    hass: HomeAssistant, start: datetime.datetime, end: datetime.datetime
) -> statistics.PlatformCompiledStatistics:
    """Compile statistics for all entities during start-end.

    Note: This will query the database and must not be run in the event loop
    """
    with recorder_util.session_scope(hass=hass) as session:
        compiled = _compile_statistics(hass, session, start, end)
    return compiled


def _compile_statistics(  # noqa: C901
    hass: HomeAssistant,
    session: Session,
    start: datetime.datetime,
    end: datetime.datetime,
) -> statistics.PlatformCompiledStatistics:
    """Compile statistics for all entities during start-end."""
    result: list[StatisticResult] = []

    sensor_states = _get_sensor_states(hass)
    wanted_statistics = _wanted_statistics(sensor_states)
    old_metadatas = statistics.get_metadata_with_session(
        hass, session, statistic_ids=[i.entity_id for i in sensor_states]
    )

    # Get history between start and end
    entities_full_history = [
        i.entity_id for i in sensor_states if "sum" in wanted_statistics[i.entity_id]
    ]
    history_list: MutableMapping[str, list[State]] = {}
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
        if "sum" not in wanted_statistics[i.entity_id]
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
    # If there are no recent state changes, the sensor's state may already be pruned
    # from the recorder. Get the state from the state machine instead.
    for _state in sensor_states:
        if _state.entity_id not in history_list:
            history_list[_state.entity_id] = [_state]

    to_process = []
    to_query = []
    for _state in sensor_states:
        entity_id = _state.entity_id
        if entity_id not in history_list:
            continue

        entity_history = history_list[entity_id]
        statistics_unit, state_unit, fstates = _normalize_states(
            hass,
            session,
            old_metadatas,
            entity_history,
            entity_id,
        )

        if not fstates:
            continue

        state_class = _state.attributes[ATTR_STATE_CLASS]

        to_process.append(
            (entity_id, statistics_unit, state_unit, state_class, fstates)
        )
        if "sum" in wanted_statistics[entity_id]:
            to_query.append(entity_id)

    last_stats = statistics.get_latest_short_term_statistics(
        hass, to_query, metadata=old_metadatas
    )
    for (  # pylint: disable=too-many-nested-blocks
        entity_id,
        statistics_unit,
        state_unit,
        state_class,
        fstates,
    ) in to_process:
        # Check metadata
        if old_metadata := old_metadatas.get(entity_id):
            if old_metadata[1]["unit_of_measurement"] != statistics_unit:
                if WARN_UNSTABLE_UNIT not in hass.data:
                    hass.data[WARN_UNSTABLE_UNIT] = set()
                if entity_id not in hass.data[WARN_UNSTABLE_UNIT]:
                    hass.data[WARN_UNSTABLE_UNIT].add(entity_id)
                    _LOGGER.warning(
                        "The unit of %s (%s) can not be converted to the unit of previously "
                        "compiled statistics (%s). Generation of long term statistics "
                        "will be suppressed unless the unit changes back to %s or a "
                        "compatible unit. "
                        "Go to %s to fix this",
                        entity_id,
                        statistics_unit,
                        old_metadata[1]["unit_of_measurement"],
                        old_metadata[1]["unit_of_measurement"],
                        LINK_DEV_STATISTICS,
                    )
                continue

        # Set meta data
        meta: StatisticMetaData = {
            "has_mean": "mean" in wanted_statistics[entity_id],
            "has_sum": "sum" in wanted_statistics[entity_id],
            "name": None,
            "source": RECORDER_DOMAIN,
            "statistic_id": entity_id,
            "unit_of_measurement": statistics_unit,
        }

        # Make calculations
        stat: StatisticData = {"start": start}
        if "max" in wanted_statistics[entity_id]:
            stat["max"] = max(*itertools.islice(zip(*fstates), 1))  # type: ignore[typeddict-item]
        if "min" in wanted_statistics[entity_id]:
            stat["min"] = min(*itertools.islice(zip(*fstates), 1))  # type: ignore[typeddict-item]

        if "mean" in wanted_statistics[entity_id]:
            stat["mean"] = _time_weighted_average(fstates, start, end)

        if "sum" in wanted_statistics[entity_id]:
            last_reset = old_last_reset = None
            new_state = old_state = None
            _sum = 0.0
            if entity_id in last_stats:
                # We have compiled history for this sensor before, use that as a starting point
                last_reset = old_last_reset = last_stats[entity_id][0]["last_reset"]
                new_state = old_state = last_stats[entity_id][0]["state"]
                _sum = last_stats[entity_id][0]["sum"] or 0.0

            for fstate, state in fstates:
                reset = False
                if (
                    state_class != STATE_CLASS_TOTAL_INCREASING
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
                            "Compiling initial sum statistics for %s, zero point set to %s",
                            entity_id,
                            fstate,
                        )
                    else:
                        _LOGGER.info(
                            "Detected new cycle for %s, last_reset set to %s (old last_reset %s)",
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
                elif state_class == STATE_CLASS_TOTAL_INCREASING:
                    try:
                        if old_state is None or reset_detected(
                            hass, entity_id, fstate, new_state, state
                        ):
                            reset = True
                            _LOGGER.info(
                                "Detected new cycle for %s, value dropped from %s to %s, "
                                "triggered by state with last_updated set to %s",
                                entity_id,
                                new_state,
                                state.last_updated.isoformat(),
                                fstate,
                            )
                    except HomeAssistantError:
                        continue

                if reset:
                    # The sensor has been reset, update the sum
                    if old_state is not None:
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
        state_class = state.attributes[ATTR_STATE_CLASS]
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        provided_statistics = DEFAULT_STATISTICS[state_class]
        if statistic_type is not None and statistic_type not in provided_statistics:
            continue

        if statistic_ids is not None and state.entity_id not in statistic_ids:
            continue

        if (
            "sum" in provided_statistics
            and ATTR_LAST_RESET not in state.attributes
            and state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
        ):
            continue

        result[state.entity_id] = {
            "has_mean": "mean" in provided_statistics,
            "has_sum": "sum" in provided_statistics,
            "name": None,
            "source": RECORDER_DOMAIN,
            "statistic_id": state.entity_id,
            "unit_of_measurement": state_unit,
        }
        continue

    return result


def validate_statistics(
    hass: HomeAssistant,
) -> dict[str, list[statistics.ValidationIssue]]:
    """Validate statistics."""
    validation_result = defaultdict(list)

    sensor_states = hass.states.all(DOMAIN)
    metadatas = statistics.get_metadata(hass, statistic_source=RECORDER_DOMAIN)
    sensor_entity_ids = {i.entity_id for i in sensor_states}
    sensor_statistic_ids = set(metadatas)

    for state in sensor_states:
        entity_id = state.entity_id
        state_class = state.attributes.get(ATTR_STATE_CLASS)
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if metadata := metadatas.get(entity_id):
            if not is_entity_recorded(hass, state.entity_id):
                # Sensor was previously recorded, but no longer is
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "entity_no_longer_recorded",
                        {"statistic_id": entity_id},
                    )
                )

            if state_class not in STATE_CLASSES:
                # Sensor no longer has a valid state class
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "unsupported_state_class",
                        {"statistic_id": entity_id, "state_class": state_class},
                    )
                )

            metadata_unit = metadata[1]["unit_of_measurement"]
            converter = statistics.STATISTIC_UNIT_TO_UNIT_CONVERTER.get(metadata_unit)
            if not converter:
                if state_unit != metadata_unit:
                    # The unit has changed, and it's not possible to convert
                    validation_result[entity_id].append(
                        statistics.ValidationIssue(
                            "units_changed",
                            {
                                "statistic_id": entity_id,
                                "state_unit": state_unit,
                                "metadata_unit": metadata_unit,
                                "supported_unit": metadata_unit,
                            },
                        )
                    )
            elif state_unit not in converter.VALID_UNITS:
                # The state unit can't be converted to the unit in metadata
                valid_units = ", ".join(sorted(converter.VALID_UNITS))
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "units_changed",
                        {
                            "statistic_id": entity_id,
                            "state_unit": state_unit,
                            "metadata_unit": metadata_unit,
                            "supported_unit": valid_units,
                        },
                    )
                )
        elif state_class in STATE_CLASSES:
            if not is_entity_recorded(hass, state.entity_id):
                # Sensor is not recorded
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "entity_not_recorded",
                        {"statistic_id": entity_id},
                    )
                )

    for statistic_id in sensor_statistic_ids - sensor_entity_ids:
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
