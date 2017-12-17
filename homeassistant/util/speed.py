"""Distance util functions."""

import logging
from numbers import Number

from homeassistant.const import (
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    SPEED,
)

_LOGGER = logging.getLogger(__name__)

VALID_UNITS = [
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    SPEED_METERS_PER_SECOND,
]


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, SPEED))
    if unit_2 not in VALID_UNITS:
        raise ValueError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, SPEED))

    if not isinstance(value, Number):
        raise TypeError('{} is not of numeric type'.format(value))

    if unit_1 == unit_2 or unit_1 not in VALID_UNITS:
        return value

    kph = value

    if unit_1 == SPEED_MILES_PER_HOUR:
        kph = __mph_to_km_per_hour(value)
    elif unit_1 == SPEED_METERS_PER_SECOND:
        kph = __m_per_sec_to_km_per_hour(value)

    result = kph

    if unit_2 == SPEED_MILES_PER_HOUR:
        result = __km_per_hour_to_mph(kph)
    elif unit_2 == SPEED_METERS_PER_SECOND:
        result = __km_per_hour_to_m_per_sec(kph)

    return result


def __mph_to_km_per_hour(mph: float) -> float:
    """Convert miles-per-hour to kilometers-per-hour."""
    return mph * 1.60934


def __m_per_sec_to_km_per_hour(mps: float) -> float:
    """Convert meters-per-second to kilometers-per-hour."""
    return mps * 3.6


def __km_per_hour_to_mph(kph: float) -> float:
    """Convert kilometers-per-hour to miles-per-hour."""
    return kph * 0.621371


def __km_per_hour_to_m_per_sec(kph: float) -> float:
    """Convert kilometers-per-hour to meters-per-second."""
    return kph * 0.277778
