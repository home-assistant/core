"""Speed util functions."""

import logging
from numbers import Number

from homeassistant.const import (
    SPEED_MS,
    SPEED_KMH,
    SPEED_FTS,
    SPEED_MPH,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    SPEED,
    UNIT_AUTOCONVERT,
)

_LOGGER = logging.getLogger(__name__)

VALID_UNITS_METRIC = [
    SPEED_MS,
    SPEED_KMH,
    UNIT_AUTOCONVERT,
]

VALID_UNITS_IMPERIAL = [
    SPEED_FTS,
    SPEED_MPH,
    UNIT_AUTOCONVERT,
]


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS_METRIC + VALID_UNITS_IMPERIAL:
        raise ValueError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, SPEED))
    if unit_2 not in VALID_UNITS_METRIC + VALID_UNITS_IMPERIAL:
        raise ValueError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, SPEED))

    if not isinstance(value, Number):
        raise TypeError('{} is not of numeric type'.format(value))

    # Match imperial to metric units
    if unit_1 in VALID_UNITS_METRIC and unit_2 is UNIT_AUTOCONVERT:
        if unit_1 == SPEED_KMH:
            unit_2 = SPEED_MPH
        if unit_1 == SPEED_MS:
            unit_2 = SPEED_FTS
    elif unit_1 in VALID_UNITS_IMPERIAL and unit_2 is UNIT_AUTOCONVERT:
        if unit_1 == SPEED_MPH:
            unit_2 = SPEED_KMH
        if unit_1 == SPEED_FTS:
            unit_2 = SPEED_MS

    if unit_1 == unit_2 or unit_1 not in (VALID_UNITS_METRIC +
                                          VALID_UNITS_IMPERIAL):
        return value

    meters = value

    if unit_1 == SPEED_MPH:
        meters = __miles_to_meters(value)
    elif unit_1 == SPEED_FTS:
        meters = __feet_to_meters(value)
    elif unit_1 == SPEED_KMH:
        meters = __kilometers_to_meters(value)

    result = meters

    if unit_2 == SPEED_MPH:
        result = __meters_to_miles(meters)
    elif unit_2 == SPEED_FTS:
        result = __meters_to_feet(meters)
    elif unit_2 == SPEED_KMH:
        result = __meters_to_kilometers(meters)

    return result


def __miles_to_meters(miles: float) -> float:
    """Convert mi/h to m/s."""
    return miles * 0.44704


def __feet_to_meters(feet: float) -> float:
    """Convert ft/s to m/s."""
    return feet * 0.3048


def __kilometers_to_meters(kilometers: float) -> float:
    """Convert km/h to m/s."""
    return kilometers * 0.277777778


def __meters_to_miles(meters: float) -> float:
    """Convert m/s to mi/s."""
    return meters * 2.23694


def __meters_to_feet(meters: float) -> float:
    """Convert m/s to ft/s."""
    return meters * 3.28084


def __meters_to_kilometers(meters: float) -> float:
    """Convert m/s to km/h."""
    return meters * 3.6
