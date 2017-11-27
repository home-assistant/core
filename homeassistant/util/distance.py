"""Distance util functions."""

import logging
from numbers import Number

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_FEET,
    LENGTH_YARD,
    LENGTH_INCHES,
    LENGTH_METERS,
    LENGTH_CENTIMETERS,
    LENGTH_MILLIMETERS,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    LENGTH,
)

_LOGGER = logging.getLogger(__name__)

VALID_UNITS = [
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_CENTIMETERS,
    LENGTH_MILLIMETERS,
    LENGTH_MILES,
    LENGTH_FEET,
    LENGTH_YARD,
    LENGTH_INCHES,
]


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, LENGTH))
    if unit_2 not in VALID_UNITS:
        raise ValueError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, LENGTH))

    if not isinstance(value, Number):
        raise TypeError('{} is not of numeric type'.format(value))

    if unit_1 == unit_2 or unit_1 not in VALID_UNITS:
        return value

    meters = value

    if unit_1 == LENGTH_MILES:
        meters = __miles_to_meters(value)
    elif unit_1 == LENGTH_FEET:
        meters = __feet_to_meters(value)
    elif unit_1 == LENGTH_INCHES:
        meters = __inches_to_meters(value)
    elif unit_1 == LENGTH_YARD:
        meters = __yards_to_meters(value)
    elif unit_1 == LENGTH_KILOMETERS:
        meters = __kilometers_to_meters(value)
    elif unit_1 == LENGTH_CENTIMETERS:
        meters = __centimeters_to_meters(value)
    elif unit_1 == LENGTH_MILLIMETERS:
        meters = __millimeters_to_meters(value)

    result = meters

    if unit_2 == LENGTH_MILES:
        result = __meters_to_miles(meters)
    elif unit_2 == LENGTH_FEET:
        result = __meters_to_feet(meters)
    elif unit_2 == LENGTH_INCHES:
        result = __meters_to_inches(meters)
    elif unit_2 == LENGTH_YARD:
        result = __meters_to_yards(meters)
    elif unit_2 == LENGTH_KILOMETERS:
        result = __meters_to_kilometers(meters)
    elif unit_2 == LENGTH_CENTIMETERS:
        result = __meters_to_centimeters(meters)
    elif unit_2 == LENGTH_MILLIMETERS:
        result = __meters_to_millimeters(meters)

    return result


def __miles_to_meters(miles: float) -> float:
    """Convert miles to meters."""
    return miles * 1609.344


def __feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    return feet * 0.3048


def __inches_to_meters(inches: float) -> float:
    """Convert inches to meters."""
    return inches * 0.0254


def __yards_to_meters(yards: float) -> float:
    """Convert yards to meters."""
    return yards * 0.9144


def __kilometers_to_meters(kilometers: float) -> float:
    """Convert kilometers to meters."""
    return kilometers * 1000


def __centimeters_to_meters(centimeters: float) -> float:
    """Convert centimeters to meters."""
    return centimeters / 100


def __millimeters_to_meters(millimeters: float) -> float:
    """Convert millimeters to meters."""
    return millimeters / 1000


def __meters_to_miles(meters: float) -> float:
    """Convert meters to miles."""
    return meters * 0.000621371


def __meters_to_feet(meters: float) -> float:
    """Convert meters to feet."""
    return meters / 0.3048


def __meters_to_inches(meters: float) -> float:
    """Convert meters to inches."""
    return meters / 0.0254


def __meters_to_yards(meters: float) -> float:
    """Convert meters to yards."""
    return meters / 0.9144


def __meters_to_kilometers(meters: float) -> float:
    """Convert meters to kilometers."""
    return meters * 0.001


def __meters_to_centimeters(meters: float) -> float:
    """Convert meters to kilometers."""
    return meters * 100


def __meters_to_millimeters(meters: float) -> float:
    """Convert meters to kilometers."""
    return meters * 1000
