"""Shared fan, swing, and temperature helpers for the climate accessory types."""

from collections.abc import Iterable
from typing import Any

from homeassistant.components.climate import (
    ATTR_FAN_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODES,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
)
from homeassistant.core import State
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .util import get_min_max, temperature_to_homekit

ORDERED_FAN_SPEEDS = [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH]
PRE_DEFINED_FAN_MODES = set(ORDERED_FAN_SPEEDS)
SWING_MODE_PREFERRED_ORDER = [SWING_ON, SWING_BOTH, SWING_HORIZONTAL, SWING_VERTICAL]
PRE_DEFINED_SWING_MODES = set(SWING_MODE_PREFERRED_ORDER)

# Minimum gap kept between the low and high set points of a range.
HEAT_COOL_DEADBAND = 5


def _lower_to_original(modes: Iterable[Any]) -> dict[str, str]:
    """Map each string mode to its original casing, keyed by the lowercase form."""
    return {mode.lower(): mode for mode in modes if isinstance(mode, str)}


def get_fan_modes_and_speeds(
    attributes: dict[str, Any],
) -> tuple[dict[str, str], list[str]]:
    """Return the fan modes and ordered predefined speeds for a climate entity.

    ``fan_modes`` maps each lowercased fan mode to its original casing.
    ``ordered_fan_speeds`` is the subset of predefined speeds the entity
    exposes, in HomeKit rotation-speed order; it is empty when the entity only
    advertises custom fan mode names.
    """
    fan_modes = _lower_to_original(attributes.get(ATTR_FAN_MODES) or [])
    ordered_fan_speeds: list[str] = []
    if PRE_DEFINED_FAN_MODES.intersection(fan_modes):
        ordered_fan_speeds = [
            speed for speed in ORDERED_FAN_SPEEDS if speed in fan_modes
        ]
    return fan_modes, ordered_fan_speeds


def get_swing_on_mode(attributes: dict[str, Any]) -> str | None:
    """Return the preferred swing-on mode for a climate entity, if any.

    The match is case insensitive and the entity's original casing is
    returned so it can be sent back to the service. Returns ``None`` when the
    entity exposes no predefined swing modes.
    """
    if not (swing_modes := attributes.get(ATTR_SWING_MODES)):
        return None
    lower_to_original = _lower_to_original(swing_modes)
    return next(
        (
            lower_to_original[swing_mode]
            for swing_mode in SWING_MODE_PREFERRED_ORDER
            if swing_mode in lower_to_original
        ),
        None,
    )


def get_swing_off_mode(attributes: dict[str, Any]) -> str:
    """Return the entity's off swing mode, preserving its original casing."""
    swing_modes = attributes.get(ATTR_SWING_MODES) or []
    return _lower_to_original(swing_modes).get(SWING_OFF, SWING_OFF)


def fan_speed_to_mode(
    ordered_fan_speeds: list[str], fan_modes: dict[str, str], speed: int
) -> str:
    """Return the climate fan mode for a HomeKit rotation speed percentage.

    The percentage is offset by one so the lowest slider step maps to the
    first ordered speed.
    """
    speed_key = percentage_to_ordered_list_item(ordered_fan_speeds, speed - 1)
    return fan_modes[speed_key]


def fan_mode_to_speed(ordered_fan_speeds: list[str], fan_mode: Any) -> int | None:
    """Return the HomeKit rotation speed percentage for a climate fan mode.

    Returns ``None`` when the mode is not one of the ordered predefined speeds.
    """
    if (
        not isinstance(fan_mode, str)
        or (fan_mode_lower := fan_mode.lower()) not in ordered_fan_speeds
    ):
        return None
    return ordered_list_item_to_percentage(ordered_fan_speeds, fan_mode_lower)


def is_swing_on(swing_mode: Any) -> bool:
    """Return whether a climate swing mode maps to HomeKit swing on."""
    return isinstance(swing_mode, str) and swing_mode.lower() in PRE_DEFINED_SWING_MODES


def get_temperature_range_from_state(
    state: State, unit: str, default_min: float, default_max: float
) -> tuple[float, float]:
    """Return the HomeKit min and max temperature range for a climate state.

    Attribute values are in the entity's unit and converted to Celsius; the
    defaults are already Celsius and used as-is. The minimum is clamped to zero
    because the Home app crashes on negative bounds.
    """
    if (min_temp := state.attributes.get(ATTR_MIN_TEMP)) is not None:
        min_temp = round(temperature_to_homekit(min_temp, unit) * 2) / 2
    else:
        min_temp = default_min

    if (max_temp := state.attributes.get(ATTR_MAX_TEMP)) is not None:
        max_temp = round(temperature_to_homekit(max_temp, unit) * 2) / 2
    else:
        max_temp = default_max

    # Handle a reversed temperature range
    min_temp, max_temp = get_min_max(min_temp, max_temp)

    min_temp = max(min_temp, 0)
    max_temp = max(max_temp, min_temp)

    return min_temp, max_temp


def temperature_attribute_to_homekit(state: State, key: str, unit: str) -> float | None:
    """Return a numeric temperature attribute converted to the HomeKit unit."""
    value = state.attributes.get(key)
    if isinstance(value, (int, float)):
        return temperature_to_homekit(value, unit)
    return None


def resolve_target_temp_range(
    current_high: float,
    current_low: float,
    new_high: float | None,
    new_low: float | None,
    min_temp: float,
    max_temp: float,
) -> tuple[float, float]:
    """Return an ordered (high, low) target range within the temperature bounds.

    The unchanged side keeps its current value and a deadband is enforced so
    the range is never inverted.
    """
    high = current_high
    low = current_low
    deadband_enforced = False
    if new_high is not None:
        high = new_high
        if high < low:
            low = high - HEAT_COOL_DEADBAND
            deadband_enforced = True
    if new_low is not None:
        low = new_low
        if low > high:
            high = low + HEAT_COOL_DEADBAND
            deadband_enforced = True
    high = min(high, max_temp)
    low = max(low, min_temp)
    # Clamping a deadband-adjusted setpoint to a bound can erase the gap it just
    # enforced; restore it by moving the setpoint that is not pinned to the bound.
    if deadband_enforced and high - low < HEAT_COOL_DEADBAND:
        if high >= max_temp:
            low = max(min_temp, high - HEAT_COOL_DEADBAND)
        else:
            high = min(max_temp, low + HEAT_COOL_DEADBAND)
    return high, low
