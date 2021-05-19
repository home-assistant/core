"""Statistics helper for sensor."""
from __future__ import annotations

import datetime
import itertools
from statistics import fmean

from homeassistant.components.recorder import history, statistics
from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import DOMAIN

DEVICE_CLASS_STATISTICS = {"temperature": {"mean", "min", "max"}, "energy": {"sum"}}


def _get_entities(hass: HomeAssistant) -> list[tuple[str, str]]:
    """Get (entity_id, device_class) of all sensors for which to compile statistics."""
    all_sensors = hass.states.all(DOMAIN)
    entity_ids = []

    for state in all_sensors:
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        state_class = state.attributes.get(ATTR_STATE_CLASS)
        if not state_class or state_class != STATE_CLASS_MEASUREMENT:
            continue
        if not device_class or device_class not in DEVICE_CLASS_STATISTICS:
            continue
        entity_ids.append((state.entity_id, device_class))
    return entity_ids


# Faster than try/except
# From https://stackoverflow.com/a/23639915
def _is_number(s: str) -> bool:  # pylint: disable=invalid-name
    """Return True if string is a number."""
    return s.replace(".", "", 1).isdigit()


def compile_statistics(
    hass: HomeAssistant, start: datetime.datetime, end: datetime.datetime
) -> dict:
    """Compile statistics for all entities during start-end.

    Note: This will query the database and must not be run in the event loop
    """
    result: dict = {}

    entities = _get_entities(hass)

    # Get history between start and end
    history_list = history.get_significant_states(  # type: ignore
        hass, start - datetime.timedelta.resolution, end, [i[0] for i in entities]
    )

    for entity_id, device_class in entities:
        wanted_statistics = DEVICE_CLASS_STATISTICS[device_class]

        if entity_id not in history_list:
            continue

        entity_history = history_list[entity_id]
        fstates = [
            (float(el.state), el) for el in entity_history if _is_number(el.state)
        ]

        if not fstates:
            continue

        result[entity_id] = {}

        # Make calculations
        if "max" in wanted_statistics:
            result[entity_id]["max"] = max(*itertools.islice(zip(*fstates), 1))
        if "min" in wanted_statistics:
            result[entity_id]["min"] = min(*itertools.islice(zip(*fstates), 1))

        # Note: The average calculation will be incorrect for unevenly spaced readings,
        # this needs to be improved by weighting with time between measurements
        if "mean" in wanted_statistics:
            result[entity_id]["mean"] = fmean(*itertools.islice(zip(*fstates), 1))

        if "sum" in wanted_statistics:
            old_last_reset = None
            old_state = None
            _sum = 0
            last_stats = statistics.get_last_statistics(hass, entity_id)  # type: ignore
            if entity_id in last_stats:
                # We have compiled history for this sensor before, use that as a starting point
                last_reset = old_last_reset = last_stats[entity_id][0]["last_reset"]
                new_state = old_state = last_stats[entity_id][0]["state"]
                _sum = last_stats[entity_id][0]["sum"]

            for fstate, state in fstates:
                if "last_reset" not in state.attributes:
                    continue
                if (last_reset := state.attributes["last_reset"]) != old_last_reset:
                    # The sensor has been reset, update the sum
                    if old_state is not None:
                        _sum += new_state - old_state
                    # ..and update the starting point
                    new_state = fstate
                    old_last_reset = last_reset
                    old_state = new_state
                else:
                    new_state = fstate

            # Update the sum with the last state
            _sum += new_state - old_state
            result[entity_id]["last_reset"] = dt_util.parse_datetime(last_reset)
            result[entity_id]["sum"] = _sum
            result[entity_id]["state"] = new_state

    return result
