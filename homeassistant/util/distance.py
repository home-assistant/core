"""Distance util functions."""

import logging
from numbers import Number

_LOGGER = logging.getLogger(__name__)

KILOMETERS_SYMBOL = 'km'
METERS_SYMBOL = 'm'
FEET_SYMBOL = 'ft'
MILES_SYMBOL = 'mi'

VALID_UNITS = [
    KILOMETERS_SYMBOL,
    METERS_SYMBOL,
    FEET_SYMBOL,
    MILES_SYMBOL,
]

UNIT_LABELS = {
    KILOMETERS_SYMBOL: 'kilometers',
    METERS_SYMBOL: 'meters',
    FEET_SYMBOL: 'feet',
    MILES_SYMBOL: 'miles',
}


def convert(value: float, unit_1: string, unit_2: string): -> float
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

    if unit_1 == MILES_SYMBOL:
        meters = __miles_to_meters(value)
    elif unit_1 == FEET_SYMBOL:
        meters = __feet_to_meters(value)
    elif unit_1 == KILOMETERS_SYMBOL:
        meters = __kilometers_to_meters(value)

    result = meters

    if unit_2 == MILES_SYMBOL:
        result = __meters_to_miles(meters)
    elif unit_2 == FEET_SYMBOL:
        result = __meters_to_feet(meters)
    elif unit_2 == KILOMETERS_SYMBOL:
        result = __meters_to_kilometers(meters)

    return result


def __miles_to_meters(miles: float):
    """Convert miles to meters."""
    return miles * 1609.344


def __feet_to_meters(feet: float):
    """Convert feet to meters."""
    return feet * 0.3048


def __kilometers_to_meters(kilometers: float):
    """Convert kilometers to meters."""
    return kilometers * 1000


def __meters_to_miles(meters: float):
    """Convert meters to miles."""
    return meters * 0.000621371


def __meters_to_feet(meters: float):
    """Convert meters to feet."""
    return meters * 3.28084


def __meters_to_kilometers(meters: float):
    """Convert meters to kilometers."""
    return meters * 0.001
