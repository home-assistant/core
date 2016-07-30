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


def __miles_to_meters(miles):
    """Convert miles to meters."""
    if not isinstance(miles, Number):
        err = '{} is not a numeric value.'.format(str(miles))
        _LOGGER.error(err)
        raise TypeError(err)

    return miles * 1609.344


def __feet_to_meters(feet):
    """Convert feet to meters."""
    if not isinstance(feet, Number):
        err = '{} is not a numeric value.'.format(str(feet))
        _LOGGER.error(err)
        raise TypeError(err)

    return feet * 0.3048


def __kilometers_to_meters(kilometers):
    """Convert kilometers to meters."""
    if not isinstance(kilometers, Number):
        err = '{} is not a numeric value.'.format(str(kilometers))
        _LOGGER.error(err)
        raise TypeError(err)

    return kilometers * 1000


def __meters_to_miles(meters):
    """Convert meters to miles."""
    if not isinstance(meters, Number):
        err = '{} is not a numeric value.'.format(str(meters))
        _LOGGER.error(err)
        raise TypeError(err)

    return meters * 0.000621371


def __meters_to_feet(meters):
    """Convert meters to feet."""
    if not isinstance(meters, Number):
        err = '{} is not a numeric value.'.format(str(meters))
        _LOGGER.error(err)
        raise TypeError(err)

    return meters * 3.28084


def __meters_to_kilometers(meters):
    """Convert meters to kilometers."""
    if not isinstance(meters, Number):
        err = '{} is not a numeric value.'.format(str(meters))
        _LOGGER.error(err)
        raise TypeError(err)

    return meters * 0.001
