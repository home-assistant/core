"""Pressure util functions."""
from numbers import Number

from homeassistant.const import (
    PRESSURE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    PRESSURE_PA,
    PRESSURE_PSI,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS = [PRESSURE_PA, PRESSURE_HPA, PRESSURE_MBAR, PRESSURE_INHG, PRESSURE_PSI]

UNIT_CONVERSION = {
    PRESSURE_PA: 1,
    PRESSURE_HPA: 1 / 100,
    PRESSURE_MBAR: 1 / 100,
    PRESSURE_INHG: 1 / 3386.389,
    PRESSURE_PSI: 1 / 6894.757,
}


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, PRESSURE))
    if unit_2 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, PRESSURE))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if unit_1 == unit_2 or unit_1 not in VALID_UNITS:
        return value

    pascals = value / UNIT_CONVERSION[unit_1]
    return pascals * UNIT_CONVERSION[unit_2]
