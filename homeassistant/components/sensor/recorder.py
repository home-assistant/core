"""Statistics helper for sensor."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
import datetime
import itertools
import logging
import math

from sqlalchemy.orm.session import Session

from homeassistant.components.recorder import (
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
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    STATE_CLASSES,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    PRESSURE_BAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    PRESSURE_PA,
    PRESSURE_PSI,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import entity_sources
import homeassistant.util.dt as dt_util
import homeassistant.util.pressure as pressure_util
import homeassistant.util.temperature as temperature_util
import homeassistant.util.volume as volume_util

from . import ATTR_LAST_RESET, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_STATISTICS: dict[str, dict[str, set[str]]] = {
    STATE_CLASS_MEASUREMENT: {
        # Deprecated, support will be removed in Home Assistant 2021.11
        DEVICE_CLASS_ENERGY: {"sum"},
        DEVICE_CLASS_GAS: {"sum"},
        DEVICE_CLASS_MONETARY: {"sum"},
    },
    STATE_CLASS_TOTAL: {},
    STATE_CLASS_TOTAL_INCREASING: {},
}
DEFAULT_STATISTICS = {
    STATE_CLASS_MEASUREMENT: {"mean", "min", "max"},
    STATE_CLASS_TOTAL: {"sum"},
    STATE_CLASS_TOTAL_INCREASING: {"sum"},
}

# Normalized units which will be stored in the statistics table
DEVICE_CLASS_UNITS = {
    DEVICE_CLASS_ENERGY: ENERGY_KILO_WATT_HOUR,
    DEVICE_CLASS_POWER: POWER_WATT,
    DEVICE_CLASS_PRESSURE: PRESSURE_PA,
    DEVICE_CLASS_TEMPERATURE: TEMP_CELSIUS,
    DEVICE_CLASS_GAS: VOLUME_CUBIC_METERS,
}

UNIT_CONVERSIONS: dict[str, dict[str, Callable]] = {
    # Convert energy to kWh
    DEVICE_CLASS_ENERGY: {
        ENERGY_KILO_WATT_HOUR: lambda x: x,
        ENERGY_WATT_HOUR: lambda x: x / 1000,
    },
    # Convert power W
    DEVICE_CLASS_POWER: {
        POWER_WATT: lambda x: x,
        POWER_KILO_WATT: lambda x: x * 1000,
    },
    # Convert pressure to Pa
    # Note: pressure_util.convert is bypassed to avoid redundant error checking
    DEVICE_CLASS_PRESSURE: {
        PRESSURE_BAR: lambda x: x / pressure_util.UNIT_CONVERSION[PRESSURE_BAR],
        PRESSURE_HPA: lambda x: x / pressure_util.UNIT_CONVERSION[PRESSURE_HPA],
        PRESSURE_INHG: lambda x: x / pressure_util.UNIT_CONVERSION[PRESSURE_INHG],
        PRESSURE_MBAR: lambda x: x / pressure_util.UNIT_CONVERSION[PRESSURE_MBAR],
        PRESSURE_PA: lambda x: x / pressure_util.UNIT_CONVERSION[PRESSURE_PA],
        PRESSURE_PSI: lambda x: x / pressure_util.UNIT_CONVERSION[PRESSURE_PSI],
    },
    # Convert temperature to °C
    # Note: temperature_util.convert is bypassed to avoid redundant error checking
    DEVICE_CLASS_TEMPERATURE: {
        TEMP_CELSIUS: lambda x: x,
        TEMP_FAHRENHEIT: temperature_util.fahrenheit_to_celsius,
        TEMP_KELVIN: temperature_util.kelvin_to_celsius,
    },
    # Convert volume to cubic meter
    DEVICE_CLASS_GAS: {
        VOLUME_CUBIC_METERS: lambda x: x,
        VOLUME_CUBIC_FEET: volume_util.cubic_feet_to_cubic_meter,
    },
}

# Keep track of entities for which a warning about decreasing value has been logged
SEEN_DIP = "sensor_seen_total_increasing_dip"
WARN_DIP = "sensor_warn_total_increasing_dip"
# Keep track of entities for which a warning about negative value has been logged
WARN_NEGATIVE = "sensor_warn_total_increasing_negative"
# Keep track of entities for which a warning about unsupported unit has been logged
WARN_UNSUPPORTED_UNIT = "sensor_warn_unsupported_unit"
WARN_UNSTABLE_UNIT = "sensor_warn_unstable_unit"


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
    device_class: str | None,
    entity_id: str,
) -> tuple[str | None, list[tuple[float, State]]]:
    """Normalize units."""
    unit = None

    if device_class not in UNIT_CONVERSIONS:
        # We're not normalizing this device class, return the state as they are
        fstates = []
        for state in entity_history:
            try:
                fstate = _parse_float(state.state)
            except (ValueError, TypeError):  # TypeError to guard for NULL state in DB
                continue
            fstates.append((fstate, state))

        if fstates:
            all_units = _get_units(fstates)
            if len(all_units) > 1:
                if WARN_UNSTABLE_UNIT not in hass.data:
                    hass.data[WARN_UNSTABLE_UNIT] = set()
                if entity_id not in hass.data[WARN_UNSTABLE_UNIT]:
                    hass.data[WARN_UNSTABLE_UNIT].add(entity_id)
                    extra = ""
                    if old_metadata := old_metadatas.get(entity_id):
                        extra = (
                            " and matches the unit of already compiled statistics "
                            f"({old_metadata[1]['unit_of_measurement']})"
                        )
                    _LOGGER.warning(
                        "The unit of %s is changing, got multiple %s, generation of long term "
                        "statistics will be suppressed unless the unit is stable%s",
                        entity_id,
                        all_units,
                        extra,
                    )
                return None, []
            unit = fstates[0][1].attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        return unit, fstates

    fstates = []

    for state in entity_history:
        try:
            fstate = _parse_float(state.state)
        except ValueError:
            continue
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        # Exclude unsupported units from statistics
        if unit not in UNIT_CONVERSIONS[device_class]:
            if WARN_UNSUPPORTED_UNIT not in hass.data:
                hass.data[WARN_UNSUPPORTED_UNIT] = set()
            if entity_id not in hass.data[WARN_UNSUPPORTED_UNIT]:
                hass.data[WARN_UNSUPPORTED_UNIT].add(entity_id)
                _LOGGER.warning("%s has unknown unit %s", entity_id, unit)
            continue

        fstates.append((UNIT_CONVERSIONS[device_class][unit](fstate), state))

    return DEVICE_CLASS_UNITS[device_class], fstates


def _suggest_report_issue(hass: HomeAssistant, entity_id: str) -> str:
    """Suggest to report an issue."""
    domain = entity_sources(hass).get(entity_id, {}).get("domain")
    custom_component = entity_sources(hass).get(entity_id, {}).get("custom_component")
    report_issue = ""
    if custom_component:
        report_issue = "report it to the custom component author."
    else:
        report_issue = (
            "create a bug report at "
            "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
        )
        if domain:
            report_issue += f"+label%3A%22integration%3A+{domain}%22"

    return report_issue


def warn_dip(hass: HomeAssistant, entity_id: str) -> None:
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
            "not strictly increasing. Please %s",
            entity_id,
            f"from integration {domain} " if domain else "",
            _suggest_report_issue(hass, entity_id),
        )


def warn_negative(hass: HomeAssistant, entity_id: str) -> None:
    """Log a warning once if a sensor with state_class_total has a negative value."""
    if WARN_NEGATIVE not in hass.data:
        hass.data[WARN_NEGATIVE] = set()
    if entity_id not in hass.data[WARN_NEGATIVE]:
        hass.data[WARN_NEGATIVE].add(entity_id)
        domain = entity_sources(hass).get(entity_id, {}).get("domain")
        _LOGGER.warning(
            "Entity %s %shas state class total_increasing, but its state is "
            "negative. Please %s",
            entity_id,
            f"from integration {domain} " if domain else "",
            _suggest_report_issue(hass, entity_id),
        )


def reset_detected(
    hass: HomeAssistant, entity_id: str, state: float, previous_state: float | None
) -> bool:
    """Test if a total_increasing sensor has been reset."""
    if previous_state is None:
        return False

    if 0.9 * previous_state <= state < previous_state:
        warn_dip(hass, entity_id)

    if state < 0:
        warn_negative(hass, entity_id)
        raise HomeAssistantError

    return state < 0.9 * previous_state


def _wanted_statistics(sensor_states: list[State]) -> dict[str, set[str]]:
    """Prepare a dict with wanted statistics for entities."""
    wanted_statistics = {}
    for state in sensor_states:
        state_class = state.attributes[ATTR_STATE_CLASS]
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        if device_class in DEVICE_CLASS_STATISTICS[state_class]:
            wanted_statistics[state.entity_id] = DEVICE_CLASS_STATISTICS[state_class][
                device_class
            ]
        else:
            wanted_statistics[state.entity_id] = DEFAULT_STATISTICS[state_class]
    return wanted_statistics


def _last_reset_as_utc_isoformat(
    last_reset_s: str | None, entity_id: str
) -> str | None:
    """Parse last_reset and convert it to UTC."""
    if last_reset_s is None:
        return None
    last_reset = dt_util.parse_datetime(last_reset_s)
    if last_reset is None:
        _LOGGER.warning(
            "Ignoring invalid last reset '%s' for %s", last_reset_s, entity_id
        )
        return None
    return dt_util.as_utc(last_reset).isoformat()


def compile_statistics(
    hass: HomeAssistant, start: datetime.datetime, end: datetime.datetime
) -> list[StatisticResult]:
    """Compile statistics for all entities during start-end.

    Note: This will query the database and must not be run in the event loop
    """
    with recorder_util.session_scope(hass=hass) as session:
        result = _compile_statistics(hass, session, start, end)
    return result


def _compile_statistics(  # noqa: C901
    hass: HomeAssistant,
    session: Session,
    start: datetime.datetime,
    end: datetime.datetime,
) -> list[StatisticResult]:
    """Compile statistics for all entities during start-end."""
    result: list[StatisticResult] = []

    sensor_states = _get_sensor_states(hass)
    wanted_statistics = _wanted_statistics(sensor_states)
    old_metadatas = statistics.get_metadata_with_session(
        hass, session, [i.entity_id for i in sensor_states], None
    )

    # Get history between start and end
    entities_full_history = [
        i.entity_id for i in sensor_states if "sum" in wanted_statistics[i.entity_id]
    ]
    history_list = {}
    if entities_full_history:
        history_list = history.get_significant_states_with_session(  # type: ignore
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
        _history_list = history.get_significant_states_with_session(  # type: ignore
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
            history_list[_state.entity_id] = (_state,)

    for _state in sensor_states:  # pylint: disable=too-many-nested-blocks
        entity_id = _state.entity_id
        if entity_id not in history_list:
            continue

        state_class = _state.attributes[ATTR_STATE_CLASS]
        device_class = _state.attributes.get(ATTR_DEVICE_CLASS)
        entity_history = history_list[entity_id]
        unit, fstates = _normalize_states(
            hass, session, old_metadatas, entity_history, device_class, entity_id
        )

        if not fstates:
            continue

        # Check metadata
        if old_metadata := old_metadatas.get(entity_id):
            if old_metadata[1]["unit_of_measurement"] != unit:
                if WARN_UNSTABLE_UNIT not in hass.data:
                    hass.data[WARN_UNSTABLE_UNIT] = set()
                if entity_id not in hass.data[WARN_UNSTABLE_UNIT]:
                    hass.data[WARN_UNSTABLE_UNIT].add(entity_id)
                    _LOGGER.warning(
                        "The unit of %s (%s) does not match the unit of already "
                        "compiled statistics (%s). Generation of long term statistics "
                        "will be suppressed unless the unit changes back to %s",
                        entity_id,
                        unit,
                        old_metadata[1]["unit_of_measurement"],
                        old_metadata[1]["unit_of_measurement"],
                    )
                continue

        # Set meta data
        meta: StatisticMetaData = {
            "statistic_id": entity_id,
            "unit_of_measurement": unit,
            "has_mean": "mean" in wanted_statistics[entity_id],
            "has_sum": "sum" in wanted_statistics[entity_id],
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
            last_stats = statistics.get_last_statistics(hass, 1, entity_id, False)
            if entity_id in last_stats:
                # We have compiled history for this sensor before, use that as a starting point
                last_reset = old_last_reset = last_stats[entity_id][0]["last_reset"]
                new_state = old_state = last_stats[entity_id][0]["state"]
                _sum = last_stats[entity_id][0]["sum"] or 0.0

            for fstate, state in fstates:

                # Deprecated, will be removed in Home Assistant 2021.11
                if (
                    "last_reset" not in state.attributes
                    and state_class == STATE_CLASS_MEASUREMENT
                ):
                    continue

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
                            hass, entity_id, fstate, new_state
                        ):
                            reset = True
                            _LOGGER.info(
                                "Detected new cycle for %s, value dropped from %s to %s",
                                entity_id,
                                new_state,
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

            # Deprecated, will be removed in Home Assistant 2021.11
            if last_reset is None and state_class == STATE_CLASS_MEASUREMENT:
                # No valid updates
                continue

            if new_state is None or old_state is None:
                # No valid updates
                continue

            # Update the sum with the last state
            _sum += new_state - old_state
            if last_reset is not None:
                stat["last_reset"] = dt_util.parse_datetime(last_reset)
            stat["sum"] = _sum
            stat["state"] = new_state

        result.append({"meta": meta, "stat": (stat,)})

    return result


def list_statistic_ids(hass: HomeAssistant, statistic_type: str | None = None) -> dict:
    """Return statistic_ids and meta data."""
    entities = _get_sensor_states(hass)

    statistic_ids = {}

    for state in entities:
        state_class = state.attributes[ATTR_STATE_CLASS]
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        native_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if device_class in DEVICE_CLASS_STATISTICS[state_class]:
            provided_statistics = DEVICE_CLASS_STATISTICS[state_class][device_class]
        else:
            provided_statistics = DEFAULT_STATISTICS[state_class]

        if statistic_type is not None and statistic_type not in provided_statistics:
            continue

        if (
            "sum" in provided_statistics
            and ATTR_LAST_RESET not in state.attributes
            and state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
        ):
            continue

        if device_class not in UNIT_CONVERSIONS:
            statistic_ids[state.entity_id] = native_unit
            continue

        if native_unit not in UNIT_CONVERSIONS[device_class]:
            continue

        statistics_unit = DEVICE_CLASS_UNITS[device_class]
        statistic_ids[state.entity_id] = statistics_unit

    return statistic_ids


def validate_statistics(
    hass: HomeAssistant,
) -> dict[str, list[statistics.ValidationIssue]]:
    """Validate statistics."""
    validation_result = defaultdict(list)

    sensor_states = _get_sensor_states(hass)

    for state in sensor_states:
        entity_id = state.entity_id
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        state_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if device_class not in UNIT_CONVERSIONS:
            metadata = statistics.get_metadata(hass, (entity_id,))
            if not metadata:
                continue
            metadata_unit = metadata[entity_id][1]["unit_of_measurement"]
            if state_unit != metadata_unit:
                validation_result[entity_id].append(
                    statistics.ValidationIssue(
                        "units_changed",
                        {
                            "statistic_id": entity_id,
                            "state_unit": state_unit,
                            "metadata_unit": metadata_unit,
                        },
                    )
                )
            continue

        if state_unit not in UNIT_CONVERSIONS[device_class]:
            validation_result[entity_id].append(
                statistics.ValidationIssue(
                    "unsupported_unit",
                    {
                        "statistic_id": entity_id,
                        "device_class": device_class,
                        "state_unit": state_unit,
                    },
                )
            )

    return validation_result
