"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from numbers import Number
from typing import TypeVar

from homeassistant.const import UNIT_NOT_RECOGNIZED_TEMPLATE

from . import (
    energy as energy_util,
    power as power_util,
    pressure as pressure_util,
    temperature as temperature_util,
    volume as volume_util,
)

_ValueT = TypeVar("_ValueT", float, None)


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    DEVICE_CLASS: str
    NORMALIZED_UNIT: str
    UNIT_CONVERSION: dict[str, float]
    VALID_UNITS: tuple[str, ...]

    @classmethod
    def convert(
        cls, value: _ValueT, from_unit: str, to_unit: str, bypass_checks: bool = False
    ) -> _ValueT:
        """Convert one unit of measurement to another."""
        if not bypass_checks:
            if from_unit not in cls.VALID_UNITS:
                raise ValueError(
                    UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, cls.DEVICE_CLASS)
                )
            if to_unit not in cls.VALID_UNITS:
                raise ValueError(
                    UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.DEVICE_CLASS)
                )
            if not isinstance(value, Number):
                raise TypeError(f"{value} is not of numeric type")

        if value is None or from_unit == to_unit:
            return value

        return cls._do_conversion(value, from_unit, to_unit)

    @classmethod
    def _do_conversion(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""
        new_value = value / cls.UNIT_CONVERSION[from_unit]
        return new_value * cls.UNIT_CONVERSION[to_unit]


class EnergyConverter(BaseUnitConverter):
    """Utility to convert energy values."""

    DEVICE_CLASS = "energy"
    NORMALIZED_UNIT = energy_util.NORMALIZED_UNIT
    UNIT_CONVERSION = energy_util.UNIT_CONVERSION
    VALID_UNITS = energy_util.VALID_UNITS


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    DEVICE_CLASS = "power"
    NORMALIZED_UNIT = power_util.NORMALIZED_UNIT
    UNIT_CONVERSION = power_util.UNIT_CONVERSION
    VALID_UNITS = power_util.VALID_UNITS


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    DEVICE_CLASS = "pressure"
    NORMALIZED_UNIT = pressure_util.NORMALIZED_UNIT
    UNIT_CONVERSION = pressure_util.UNIT_CONVERSION
    VALID_UNITS = pressure_util.VALID_UNITS


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    DEVICE_CLASS = "temperature"
    NORMALIZED_UNIT = temperature_util.NORMALIZED_UNIT
    VALID_UNITS = temperature_util.VALID_UNITS

    @classmethod
    def _do_conversion(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""
        return temperature_util.convert_no_checks(value, from_unit, to_unit)


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    DEVICE_CLASS = "volume"
    NORMALIZED_UNIT = volume_util.NORMALIZED_UNIT
    UNIT_CONVERSION = volume_util.UNIT_CONVERSION
    VALID_UNITS = volume_util.VALID_UNITS
