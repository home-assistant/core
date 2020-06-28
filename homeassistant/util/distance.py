"""Distance util functions."""

import logging
from numbers import Number

from homeassistant.const import (
    LENGTH,
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

_LOGGER = logging.getLogger(__name__)

VALID_UNITS = [LENGTH_KILOMETERS, LENGTH_MILES, LENGTH_FEET, LENGTH_METERS]


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, LENGTH))
    if unit_2 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, LENGTH))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if unit_1 == unit_2 or unit_1 not in VALID_UNITS:
        return value

    meters: float = value

    if unit_1 == LENGTH_MILES:
        meters = __miles_to_meters(value)
    elif unit_1 == LENGTH_FEET:
        meters = __feet_to_meters(value)
    elif unit_1 == LENGTH_KILOMETERS:
        meters = __kilometers_to_meters(value)

    result = meters

    if unit_2 == LENGTH_MILES:
        result = __meters_to_miles(meters)
    elif unit_2 == LENGTH_FEET:
        result = __meters_to_feet(meters)
    elif unit_2 == LENGTH_KILOMETERS:
        result = __meters_to_kilometers(meters)

    return result


def __miles_to_meters(miles: float) -> float:
    """Convert miles to meters."""
    return miles * 1609.344


def __feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    return feet * 0.3048


def __kilometers_to_meters(kilometers: float) -> float:
    """Convert kilometers to meters."""
    return kilometers * 1000


def __meters_to_miles(meters: float) -> float:
    """Convert meters to miles."""
    return meters * 0.000621371


def __meters_to_feet(meters: float) -> float:
    """Convert meters to feet."""
    return meters * 3.28084


def __meters_to_kilometers(meters: float) -> float:
    """Convert meters to kilometers."""
    return meters * 0.001
