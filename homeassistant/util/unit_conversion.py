"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
from numbers import Number

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


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    NORMALIZED_UNIT: str
    VALID_UNITS: tuple[str, ...]
    convert: Callable[[float, str, str], float]


class BaseUnitConverterWithUnitConversion(BaseUnitConverter):
    """Define the format of a conversion utility."""

    DEVICE_CLASS: str
    UNIT_CONVERSION: dict[str, float]

    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""
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

        if from_unit == to_unit:
            return value

        new_value = value / cls.UNIT_CONVERSION[from_unit]
        return new_value * cls.UNIT_CONVERSION[to_unit]


class EnergyConverter(BaseUnitConverterWithUnitConversion):
    """Utility to convert energy values."""

    DEVICE_CLASS = "energy"
    NORMALIZED_UNIT = ENERGY_KILO_WATT_HOUR
    UNIT_CONVERSION: dict[str, float] = {
        ENERGY_WATT_HOUR: 1 * 1000,
        ENERGY_KILO_WATT_HOUR: 1,
        ENERGY_MEGA_WATT_HOUR: 1 / 1000,
    }
    VALID_UNITS: tuple[str, ...] = (
        ENERGY_WATT_HOUR,
        ENERGY_KILO_WATT_HOUR,
        ENERGY_MEGA_WATT_HOUR,
    )


class PowerConverter(BaseUnitConverterWithUnitConversion):
    """Utility to convert power values."""

    DEVICE_CLASS = "power"
    NORMALIZED_UNIT = POWER_WATT
    UNIT_CONVERSION: dict[str, float] = {
        POWER_WATT: 1,
        POWER_KILO_WATT: 1 / 1000,
    }
    VALID_UNITS: tuple[str, ...] = (
        POWER_WATT,
        POWER_KILO_WATT,
    )


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    NORMALIZED_UNIT = PRESSURE_PA
    VALID_UNITS = pressure_util.VALID_UNITS
    convert = pressure_util.convert


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    NORMALIZED_UNIT = TEMP_CELSIUS
    VALID_UNITS = temperature_util.VALID_UNITS
    convert = temperature_util.convert


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    NORMALIZED_UNIT = VOLUME_CUBIC_METERS
    VALID_UNITS = volume_util.VALID_UNITS
    convert = volume_util.convert
