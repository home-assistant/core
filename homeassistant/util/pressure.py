"""Pressure util functions."""
from __future__ import annotations

from homeassistant.const import (  # pylint: disable=unused-import # noqa: F401
    PRESSURE,
    PRESSURE_BAR,
    PRESSURE_CBAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_KPA,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    PRESSURE_PA,
    PRESSURE_PSI,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

from .unit_conversion import PressureConverter

UNIT_CONVERSION: dict[str, float] = PressureConverter.UNIT_CONVERSION
VALID_UNITS = PressureConverter.VALID_UNITS


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    # Need to add warning when core migration finished
    return PressureConverter.convert(value, from_unit, to_unit)
