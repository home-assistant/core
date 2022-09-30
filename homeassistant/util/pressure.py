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
from homeassistant.helpers.frame import report

from .unit_conversion import PressureConverter

VALID_UNITS = PressureConverter.VALID_UNITS
UNIT_CONVERSION: dict[str, float] = {
    PRESSURE_PA: 1,
    PRESSURE_HPA: 1 / 100,
    PRESSURE_KPA: 1 / 1000,
    PRESSURE_BAR: 1 / 100000,
    PRESSURE_CBAR: 1 / 1000,
    PRESSURE_MBAR: 1 / 100,
    PRESSURE_INHG: 1 / 3386.389,
    PRESSURE_PSI: 1 / 6894.757,
    PRESSURE_MMHG: 1 / 133.322,
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    report(
        "uses pressure utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.PressureConverter instead",
        error_if_core=False,
    )
    return PressureConverter.convert(value, from_unit, to_unit)
