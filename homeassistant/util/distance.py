"""Distance util functions."""

import logging
from numbers import Number

_LOGGER = logging.getLogger(__name__)
VALID_UNITS = ['km', 'm', 'ft', 'mi']


def kilometers_to_miles(kilometers):
    """Convert the given kilometers to miles."""
    if not isinstance(kilometers, Number):
        raise TypeError(str(kilometers) + ' is not of numeric type')

    return kilometers * 0.621371


def miles_to_kilometers(miles):
    """Convert the given miles to kilometers."""
    if not isinstance(miles, Number):
        raise TypeError(str(miles) + ' is not of numeric type')

    return miles * 1.60934


def kilometers_to_meters(kilometers):
    """Convert the given kilometers to meters."""
    if not isinstance(kilometers, Number):
        raise TypeError(str(kilometers) + ' is not of numeric type')

    return kilometers * 1000


def meters_to_kilometers(meters):
    """Convert the given meters to kilometers."""
    if not isinstance(meters, Number):
        raise TypeError(str(meters) + ' is not of numeric type')

    return meters * 0.001


def meters_to_feet(meters):
    """Convert the given meters to feet."""
    if not isinstance(meters, Number):
        raise TypeError(str(meters) + ' is not of numeric type')

    return meters * 3.28084


def feet_to_meters(feet):
    """Convert the given feet to meters."""
    if not isinstance(feet, Number):
        raise TypeError(str(feet) + ' is not of numeric type')

    return feet * 0.3048


def feet_to_miles(feet):
    """Convert the given feet to miles."""
    if not isinstance(feet, Number):
        raise TypeError(str(feet) + ' is not of numeric type')

    return feet * 0.000189394


def miles_to_feet(miles):
    """Convert the given miles to feet."""
    if not isinstance(miles, Number):
        raise TypeError(str(miles) + ' is not of numeric type')

    return miles * 5280


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

    result = None

    if unit_1 == 'mi':
        if unit_2 == 'km':
            result = miles_to_kilometers(value)
        elif unit_2 == 'm':
            result = kilometers_to_meters(miles_to_kilometers(value))
        elif unit_2 == 'ft':
            result = miles_to_feet(value)
    elif unit_1 == 'ft':
        if unit_2 == 'mi':
            result = feet_to_miles(value)
        elif unit_2 == 'km':
            result = meters_to_kilometers(feet_to_meters(value))
        elif unit_2 == 'm':
            result = feet_to_meters(value)
    elif unit_1 == 'km':
        if unit_2 == 'mi':
            result = kilometers_to_miles(value)
        elif unit_2 == 'm':
            result = kilometers_to_meters(value)
        elif unit_2 == 'ft':
            result = meters_to_feet(kilometers_to_meters(value))
    elif unit_1 == 'm':
        if unit_2 == 'km':
            result = meters_to_kilometers(value)
        elif unit_2 == 'ft':
            result = meters_to_feet(value)
        elif unit_2 == 'mi':
            result = kilometers_to_miles(meters_to_kilometers(value))

    return result
