"""Statistics helper for sensor."""
from __future__ import annotations

import datetime
import statistics

from homeassistant.components.recorder import history
from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from . import DOMAIN

DEVICE_CLASS_STATISTICS = {"temperature": {"mean", "min", "max"}}


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
        hass, start, end, [i[0] for i in entities]
    )

    for entity_id, device_class in entities:
        wanted_statistics = DEVICE_CLASS_STATISTICS[device_class]

        if entity_id not in history_list:
            continue

        entity_history = history_list[entity_id]
        fstates = [float(el.state) for el in entity_history if _is_number(el.state)]

        if not fstates:
            continue

        result[entity_id] = {}

        # Make calculations
        if "max" in wanted_statistics:
            result[entity_id]["max"] = max(fstates)
        if "min" in wanted_statistics:
            result[entity_id]["min"] = min(fstates)

        # Note: The average calculation will be incorrect for unevenly spaced readings,
        # this needs to be improved by weighting with time between measurements
        if "mean" in wanted_statistics:
            result[entity_id]["mean"] = statistics.fmean(fstates)

    return result
