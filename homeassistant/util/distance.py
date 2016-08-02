"""Distance util functions."""

import logging
from numbers import Number

from homeassistant.const import (LENGTH_KILOMETERS, LENGTH_MILES, LENGTH_FEET,
                                 LENGTH_METERS)

_LOGGER = logging.getLogger(__name__)

KILOMETERS_SYMBOL = 'km'
METERS_SYMBOL = 'm'
FEET_SYMBOL = 'ft'
MILES_SYMBOL = 'mi'

VALID_UNITS = [
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_FEET,
    LENGTH_METERS,
]


def convert(value, unit_1, unit_2):
    """Convert one unit of measurement to another."""
    if not isinstance(value, Number):
        raise TypeError(str(value) + ' is not of numeric type')

    if unit_1 == unit_2:
        return value

    if unit_1 not in VALID_UNITS:
        _LOGGER.error('Unknown unit of measure: ' + str(unit_1))
        raise ValueError('Unknown unit of measure: ' + str(unit_1))
    elif unit_2 not in VALID_UNITS:
        _LOGGER.error('Unknown unit of measure: ' + str(unit_2))
        raise ValueError('Unknown unit of measure: ' + str(unit_2))

    meters = value

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


def __miles_to_meters(miles):
    """Convert miles to meters."""
    return miles * 1609.344


def __feet_to_meters(feet):
    """Convert feet to meters."""
    return feet * 0.3048


def __kilometers_to_meters(kilometers):
    """Convert kilometers to meters."""
    return kilometers * 1000


def __meters_to_miles(meters):
    """Convert meters to miles."""
    return meters * 0.000621371


def __meters_to_feet(meters):
    """Convert meters to feet."""
    return meters * 3.28084


def __meters_to_kilometers(meters):
    """Convert meters to kilometers."""
    return meters * 0.001
