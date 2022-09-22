"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from numbers import Number
from typing import TypeVar

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    PRESSURE_PA,
    TEMP_CELSIUS,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME_CUBIC_METERS,
)

from . import (
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
    NORMALIZED_UNIT = ENERGY_KILO_WATT_HOUR
    UNIT_CONVERSION = {
        ENERGY_WATT_HOUR: 1 * 1000,
        ENERGY_KILO_WATT_HOUR: 1,
        ENERGY_MEGA_WATT_HOUR: 1 / 1000,
    }
    VALID_UNITS = (
        ENERGY_WATT_HOUR,
        ENERGY_KILO_WATT_HOUR,
        ENERGY_MEGA_WATT_HOUR,
    )


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    DEVICE_CLASS = "power"
    NORMALIZED_UNIT = POWER_WATT
    UNIT_CONVERSION = {
        POWER_WATT: 1,
        POWER_KILO_WATT: 1 / 1000,
    }
    VALID_UNITS = (
        POWER_WATT,
        POWER_KILO_WATT,
    )


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    DEVICE_CLASS = "pressure"
    NORMALIZED_UNIT = PRESSURE_PA
    UNIT_CONVERSION = pressure_util.UNIT_CONVERSION
    VALID_UNITS = pressure_util.VALID_UNITS


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    DEVICE_CLASS = "temperature"
    NORMALIZED_UNIT = TEMP_CELSIUS
    VALID_UNITS = temperature_util.VALID_UNITS

    @classmethod
    def _do_conversion(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""
        return temperature_util.convert_no_checks(value, from_unit, to_unit)


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    DEVICE_CLASS = "volume"
    NORMALIZED_UNIT = VOLUME_CUBIC_METERS
    UNIT_CONVERSION = volume_util.UNIT_CONVERSION
    VALID_UNITS = volume_util.VALID_UNITS
