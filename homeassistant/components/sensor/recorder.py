"""Statistics helper for sensor."""
from __future__ import annotations

import datetime
import itertools
import logging
from typing import Callable

from homeassistant.components.recorder import history, statistics
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
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
    STATE_CLASS_TOTAL_INCREASING: {},
}
DEFAULT_STATISTICS = {
    STATE_CLASS_MEASUREMENT: {"mean", "min", "max"},
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
# Keep track of entities for which a warning about unsupported unit has been logged
WARN_UNSUPPORTED_UNIT = "sensor_warn_unsupported_unit"
WARN_UNSTABLE_UNIT = "sensor_warn_unstable_unit"


def _get_entities(hass: HomeAssistant) -> list[tuple[str, str, str | None]]:
    """Get (entity_id, state_class, device_class) of all sensors for which to compile statistics."""
    all_sensors = hass.states.all(DOMAIN)
    entity_ids = []

    for state in all_sensors:
        if (state_class := state.attributes.get(ATTR_STATE_CLASS)) not in STATE_CLASSES:
            continue
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        entity_ids.append((state.entity_id, state_class, device_class))

    return entity_ids


def _time_weighted_average(
    fstates: list[tuple[float, State]], start: datetime.datetime, end: datetime.datetime
) -> float:
    """Calculate a time weighted average.

    The average is calculated by, weighting the states by duration in seconds between
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


def _normalize_states(
    hass: HomeAssistant,
    entity_history: list[State],
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
                fstates.append((float(state.state), state))
            except ValueError:
                continue

        if fstates:
            all_units = _get_units(fstates)
            if len(all_units) > 1:
                if WARN_UNSTABLE_UNIT not in hass.data:
                    hass.data[WARN_UNSTABLE_UNIT] = set()
                if entity_id not in hass.data[WARN_UNSTABLE_UNIT]:
                    hass.data[WARN_UNSTABLE_UNIT].add(entity_id)
                    extra = ""
                    if old_metadata := statistics.get_metadata(hass, entity_id):
                        extra = (
                            " and matches the unit of already compiled statistics "
                            f"({old_metadata['unit_of_measurement']})"
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
            fstate = float(state.state)
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
        except ValueError:
            continue

    return DEVICE_CLASS_UNITS[device_class], fstates


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
            "not strictly increasing. Please create a bug report at %s",
            entity_id,
            f"from integration {domain} " if domain else "",
            "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
            "+label%3A%22integration%3A+recorder%22",
        )


def reset_detected(
    hass: HomeAssistant, entity_id: str, state: float, previous_state: float | None
) -> bool:
    """Test if a total_increasing sensor has been reset."""
    if previous_state is None:
        return False

    if 0.9 * previous_state <= state < previous_state:
        warn_dip(hass, entity_id)

    return state < 0.9 * previous_state


def _wanted_statistics(
    entities: list[tuple[str, str, str | None]]
) -> dict[str, set[str]]:
    """Prepare a dict with wanted statistics for entities."""
    wanted_statistics = {}
    for entity_id, state_class, device_class in entities:
        if device_class in DEVICE_CLASS_STATISTICS[state_class]:
            wanted_statistics[entity_id] = DEVICE_CLASS_STATISTICS[state_class][
                device_class
            ]
        else:
            wanted_statistics[entity_id] = DEFAULT_STATISTICS[state_class]
    return wanted_statistics


def compile_statistics(  # noqa: C901
    hass: HomeAssistant, start: datetime.datetime, end: datetime.datetime
) -> dict:
    """Compile statistics for all entities during start-end.

    Note: This will query the database and must not be run in the event loop
    """
    result: dict = {}

    entities = _get_entities(hass)

    wanted_statistics = _wanted_statistics(entities)

    # Get history between start and end
    entities_full_history = [i[0] for i in entities if "sum" in wanted_statistics[i[0]]]
    history_list = {}
    if entities_full_history:
        history_list = history.get_significant_states(  # type: ignore
            hass,
            start - datetime.timedelta.resolution,
            end,
            entity_ids=entities_full_history,
            significant_changes_only=False,
        )
    entities_significant_history = [
        i[0] for i in entities if "sum" not in wanted_statistics[i[0]]
    ]
    if entities_significant_history:
        _history_list = history.get_significant_states(  # type: ignore
            hass,
            start - datetime.timedelta.resolution,
            end,
            entity_ids=entities_significant_history,
        )
        history_list = {**history_list, **_history_list}

    for entity_id, state_class, device_class in entities:
        if entity_id not in history_list:
            continue

        entity_history = history_list[entity_id]
        unit, fstates = _normalize_states(hass, entity_history, device_class, entity_id)

        if not fstates:
            continue

        # Check metadata
        if old_metadata := statistics.get_metadata(hass, entity_id):
            if old_metadata["unit_of_measurement"] != unit:
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
                        old_metadata["unit_of_measurement"],
                        old_metadata["unit_of_measurement"],
                    )
                continue

        result[entity_id] = {}

        # Set meta data
        result[entity_id]["meta"] = {
            "unit_of_measurement": unit,
            "has_mean": "mean" in wanted_statistics[entity_id],
            "has_sum": "sum" in wanted_statistics[entity_id],
        }

        # Make calculations
        stat: dict = {}
        if "max" in wanted_statistics[entity_id]:
            stat["max"] = max(*itertools.islice(zip(*fstates), 1))
        if "min" in wanted_statistics[entity_id]:
            stat["min"] = min(*itertools.islice(zip(*fstates), 1))

        if "mean" in wanted_statistics[entity_id]:
            stat["mean"] = _time_weighted_average(fstates, start, end)

        if "sum" in wanted_statistics[entity_id]:
            last_reset = old_last_reset = None
            new_state = old_state = None
            _sum = 0
            last_stats = statistics.get_last_statistics(hass, 1, entity_id)
            if entity_id in last_stats:
                # We have compiled history for this sensor before, use that as a starting point
                last_reset = old_last_reset = last_stats[entity_id][0]["last_reset"]
                new_state = old_state = last_stats[entity_id][0]["state"]
                _sum = last_stats[entity_id][0]["sum"] or 0

            for fstate, state in fstates:

                # Deprecated, will be removed in Home Assistant 2021.10
                if (
                    "last_reset" not in state.attributes
                    and state_class == STATE_CLASS_MEASUREMENT
                ):
                    continue

                reset = False
                if (
                    state_class != STATE_CLASS_TOTAL_INCREASING
                    and (last_reset := state.attributes.get("last_reset"))
                    != old_last_reset
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
                elif state_class == STATE_CLASS_TOTAL_INCREASING and (
                    old_state is None
                    or reset_detected(hass, entity_id, fstate, new_state)
                ):
                    reset = True
                    _LOGGER.info(
                        "Detected new cycle for %s, value dropped from %s to %s",
                        entity_id,
                        fstate,
                        new_state,
                    )

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
                result.pop(entity_id)
                continue

            if new_state is None or old_state is None:
                # No valid updates
                result.pop(entity_id)
                continue

            # Update the sum with the last state
            _sum += new_state - old_state
            if last_reset is not None:
                stat["last_reset"] = dt_util.parse_datetime(last_reset)
            stat["sum"] = _sum
            stat["state"] = new_state

        result[entity_id]["stat"] = stat

    return result


def list_statistic_ids(hass: HomeAssistant, statistic_type: str | None = None) -> dict:
    """Return statistic_ids and meta data."""
    entities = _get_entities(hass)

    statistic_ids = {}

    for entity_id, state_class, device_class in entities:
        if device_class in DEVICE_CLASS_STATISTICS[state_class]:
            provided_statistics = DEVICE_CLASS_STATISTICS[state_class][device_class]
        else:
            provided_statistics = DEFAULT_STATISTICS[state_class]

        if statistic_type is not None and statistic_type not in provided_statistics:
            continue

        state = hass.states.get(entity_id)
        assert state

        if (
            "sum" in provided_statistics
            and ATTR_LAST_RESET not in state.attributes
            and state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
        ):
            continue

        metadata = statistics.get_metadata(hass, entity_id)
        if metadata:
            native_unit: str | None = metadata["unit_of_measurement"]
        else:
            native_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        if device_class not in UNIT_CONVERSIONS:
            statistic_ids[entity_id] = native_unit
            continue

        if native_unit not in UNIT_CONVERSIONS[device_class]:
            continue

        statistics_unit = DEVICE_CLASS_UNITS[device_class]
        statistic_ids[entity_id] = statistics_unit

    return statistic_ids
