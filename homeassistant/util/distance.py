"""Distance util functions."""
from __future__ import annotations

from numbers import Number
from typing import Callable

from homeassistant.const import (
    LENGTH,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_FEET,
    LENGTH_METERS,
    LENGTH_CENTIMETERS,
    LENGTH_MILLIMETERS,
    LENGTH_INCHES,
    LENGTH_YARD,
)

TO_METERS: dict[str, Callable[[float], float]] = {
    LENGTH_METERS: lambda meters: meters,
    LENGTH_MILES: lambda miles: miles * 1609.344,
    LENGTH_YARD: lambda yards: yards * 0.9144,
    LENGTH_FEET: lambda feet: feet * 0.3048,
    LENGTH_INCHES: lambda inches: inches * 0.0254,
    LENGTH_KILOMETERS: lambda kilometers: kilometers * 1000,
    LENGTH_CENTIMETERS: lambda centimeters: centimeters * 0.01,
    LENGTH_MILLIMETERS: lambda millimeters: millimeters * 0.001,
}

METERS_TO: dict[str, Callable[[float], float]] = {
    LENGTH_METERS: lambda meters: meters,
    LENGTH_MILES: lambda meters: meters * 0.000621371,
    LENGTH_YARD: lambda meters: meters * 1.09361,
    LENGTH_FEET: lambda meters: meters * 3.28084,
    LENGTH_INCHES: lambda meters: meters * 39.3701,
    LENGTH_KILOMETERS: lambda meters: meters * 0.001,
    LENGTH_CENTIMETERS: lambda meters: meters * 100,
    LENGTH_MILLIMETERS: lambda meters: meters * 1000,
}


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

    meters: float = TO_METERS[unit_1](value)

    return METERS_TO[unit_2](meters)
