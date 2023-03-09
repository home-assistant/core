"""Pressure util functions."""
from __future__ import annotations

# pylint: disable-next=unused-import,hass-deprecated-import
from homeassistant.const import (  # noqa: F401
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

# pylint: disable-next=protected-access
UNIT_CONVERSION: dict[str | None, float] = PressureConverter._UNIT_CONVERSION
VALID_UNITS = PressureConverter.VALID_UNITS


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    report(
        (
            "uses pressure utility. This is deprecated since 2022.10 and will "
            "stop working in Home Assistant 2023.4, it should be updated to use "
            "unit_conversion.PressureConverter instead"
        ),
        error_if_core=False,
    )
    return PressureConverter.convert(value, from_unit, to_unit)
