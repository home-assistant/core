"""Distance util functions."""

import logging

_LOGGER = logging.getLogger(__name__)
VALID_UNITS = ['km', 'm', 'ft', 'mi']


def kilometers_to_miles(km):
    """Convert the given kilometers to miles."""
    if not isinstance(km, (int, long, float)):
        raise TypeError(str(km) ' is not of numeric type')

    return km * 0.621371


def miles_to_kilometers(mi):
    """Convert the given miles to kilometers."""
    if not isinstance(mi, (int, long, float)):
        raise TypeError(str(mi) ' is not of numeric type')

    return mi * 1.60934


def kilometers_to_meters(km):
    """Convert the given kilometers to meters."""
    if not isinstance(km, (int, long, float)):
        raise TypeError(str(km) ' is not of numeric type')

    return km * 1000


def meters_to_kilometers(m):
    """Convert the given meters to kilometers."""
    if not isinstance(m, (int, long, float)):
        raise TypeError(str(m) ' is not of numeric type')

    return m * 0.001


def meters_to_feet(m):
    """Convert the given meters to feet."""
    if not isinstance(m, (int, long, float)):
        raise TypeError(str(m) ' is not of numeric type')

    return m * 3.28084


def feet_to_meters(ft):
    """Convert the given feet to meters."""
    if not isinstance(ft, (int, long, float)):
        raise TypeError(str(ft) ' is not of numeric type')

    return ft * 0.3048


def feet_to_miles(ft):
    """Convert the given feet to miles."""
    if not isinstance(ft, (int, long, float)):
        raise TypeError(str(ft) ' is not of numeric type')

    return ft * 0.000189394


def miles_to_ft(mi):
    """Convert the given miles to feet."""
    if not isinstance(mi, (int, long, float)):
        raise TypeError(str(mi) ' is not of numeric type')

    return mi * 5280


def convert(value, unit_1, unit_2):
    """Convert one unit of measurement to another."""
    if not isinstance(value, (int, long, float)):
        raise TypeError(str(value) ' is not of numeric type')

    if unit_1 == unit_2:
        return value

    if unit_1 not in VALID_UNITS:
        _LOGGER.error('Unknown unit of measure: ' + str(unit_1))
        raise ValueError('Unknown unit of measure: ' + str(unit_1))
    elif unit_2 not in VALID_UNITS:
        _LOGGER.error('Unknown unit of measure: ' + str(unit_2))
        raise ValueError('Unknown unit of measure: ' + str(unit_2))

    if unit_1 == 'mi':
        if unit_2 == 'km':
            return miles_to_kilometers(value)
        elif unit_2 == 'm':
            return kilometers_to_meters(miles_to_kilometers(value))
        elif unit_2 == 'ft':
            return miles_to_ft(value)
    elif unit_1 == 'ft':
        if unit_2 == 'mi':
            return feet_to_miles(value)
        elif unit_2 == 'km':
            return miles_to_kilometers(feet_to_meters(value))
        elif unit_2 == 'm':
            return feet_to_meters(value)
    elif unit_1 == 'km':
        if unit_2 == 'mi':
            return kilometers_to_miles(value)
        elif unit_2 == 'm':
            return kilometers_to_meters(value)
        elif unit_2 == 'ft':
            return kilometers_to_meters(meters_to_feet(value))
    elif unit_1 == 'm':
        if unit_2 == 'km':
            return meters_to_kilometers(value)
        elif unit_2 == 'ft':
            return meters_to_feet(value)
        elif unit_2 == 'mi':
            return kilometers_to_miles(meters_to_kilometers(value))

    return None
