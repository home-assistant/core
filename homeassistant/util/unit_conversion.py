"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from abc import abstractmethod
from numbers import Number
from typing import TypeVar

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    PRESSURE_BAR,
    PRESSURE_CBAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_KPA,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    PRESSURE_PA,
    PRESSURE_PSI,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
)

from .distance import FOOT_TO_M, IN_TO_M

_ValueT = TypeVar("_ValueT", float, None)

# Volume conversion constants
_L_TO_CUBIC_METER = 0.001  # 1 L = 0.001 m³
_ML_TO_CUBIC_METER = 0.001 * _L_TO_CUBIC_METER  # 1 mL = 0.001 L
_GALLON_TO_CUBIC_METER = 231 * pow(IN_TO_M, 3)  # US gallon is 231 cubic inches
_FLUID_OUNCE_TO_CUBIC_METER = _GALLON_TO_CUBIC_METER / 128  # 128 fl. oz. in a US gallon
_CUBIC_FOOT_TO_CUBIC_METER = pow(FOOT_TO_M, 3)


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    UNIT_CLASS: str
    NORMALIZED_UNIT: str
    VALID_UNITS: tuple[str, ...]

    @classmethod
    def _check_arguments(cls, value: _ValueT, from_unit: str, to_unit: str) -> None:
        """Check that arguments are all valid."""
        if from_unit not in cls.VALID_UNITS:
            raise ValueError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, cls.UNIT_CLASS)
            )
        if to_unit not in cls.VALID_UNITS:
            raise ValueError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )

        if not isinstance(value, Number):
            raise TypeError(f"{value} is not of numeric type")

    @classmethod
    @abstractmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""

    @classmethod
    def from_normalized_unit(cls, value: _ValueT, to_unit: str) -> _ValueT:
        """Convert one unit of measurement to another."""
        if value is None:
            return value
        return cls.convert(value, cls.NORMALIZED_UNIT, to_unit)

    @classmethod
    def to_normalized_unit(cls, value: float, from_unit: str) -> float:
        """Convert one unit of measurement to another."""
        return cls.convert(value, from_unit, cls.NORMALIZED_UNIT)


class BaseUnitConverterWithUnitConversion(BaseUnitConverter):
    """Define the format of a conversion utility."""

    UNIT_CONVERSION: dict[str, float]

    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""
        cls._check_arguments(value, from_unit, to_unit)

        if from_unit == to_unit:
            return value

        new_value = value / cls.UNIT_CONVERSION[from_unit]
        return new_value * cls.UNIT_CONVERSION[to_unit]


class EnergyConverter(BaseUnitConverterWithUnitConversion):
    """Utility to convert energy values."""

    UNIT_CLASS = "energy"
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

    UNIT_CLASS = "power"
    NORMALIZED_UNIT = POWER_WATT
    UNIT_CONVERSION: dict[str, float] = {
        POWER_WATT: 1,
        POWER_KILO_WATT: 1 / 1000,
    }
    VALID_UNITS: tuple[str, ...] = (
        POWER_WATT,
        POWER_KILO_WATT,
    )


class PressureConverter(BaseUnitConverterWithUnitConversion):
    """Utility to convert pressure values."""

    UNIT_CLASS = "pressure"
    NORMALIZED_UNIT = PRESSURE_PA
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
    VALID_UNITS: tuple[str, ...] = (
        PRESSURE_PA,
        PRESSURE_HPA,
        PRESSURE_KPA,
        PRESSURE_BAR,
        PRESSURE_CBAR,
        PRESSURE_MBAR,
        PRESSURE_INHG,
        PRESSURE_PSI,
        PRESSURE_MMHG,
    )


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    UNIT_CLASS = "temperature"
    NORMALIZED_UNIT = TEMP_CELSIUS
    VALID_UNITS: tuple[str, ...] = (
        TEMP_CELSIUS,
        TEMP_FAHRENHEIT,
        TEMP_KELVIN,
    )

    @classmethod
    def convert(
        cls, value: float, from_unit: str, to_unit: str, *, interval: bool = False
    ) -> float:
        """Convert a temperature from one unit to another."""
        cls._check_arguments(value, from_unit, to_unit)

        if from_unit == to_unit:
            return value

        if from_unit == TEMP_CELSIUS:
            if to_unit == TEMP_FAHRENHEIT:
                return cls.celsius_to_fahrenheit(value, interval)
            # kelvin
            return cls.celsius_to_kelvin(value, interval)

        if from_unit == TEMP_FAHRENHEIT:
            if to_unit == TEMP_CELSIUS:
                return cls.fahrenheit_to_celsius(value, interval)
            # kelvin
            return cls.celsius_to_kelvin(
                cls.fahrenheit_to_celsius(value, interval), interval
            )

        # from_unit == kelvin
        if to_unit == TEMP_CELSIUS:
            return cls.kelvin_to_celsius(value, interval)
        # fahrenheit
        return cls.celsius_to_fahrenheit(
            cls.kelvin_to_celsius(value, interval), interval
        )

    @classmethod
    def fahrenheit_to_celsius(cls, fahrenheit: float, interval: bool = False) -> float:
        """Convert a temperature in Fahrenheit to Celsius."""
        if interval:
            return fahrenheit / 1.8
        return (fahrenheit - 32.0) / 1.8

    @classmethod
    def kelvin_to_celsius(cls, kelvin: float, interval: bool = False) -> float:
        """Convert a temperature in Kelvin to Celsius."""
        if interval:
            return kelvin
        return kelvin - 273.15

    @classmethod
    def celsius_to_fahrenheit(cls, celsius: float, interval: bool = False) -> float:
        """Convert a temperature in Celsius to Fahrenheit."""
        if interval:
            return celsius * 1.8
        return celsius * 1.8 + 32.0

    @classmethod
    def celsius_to_kelvin(cls, celsius: float, interval: bool = False) -> float:
        """Convert a temperature in Celsius to Kelvin."""
        if interval:
            return celsius
        return celsius + 273.15


class VolumeConverter(BaseUnitConverterWithUnitConversion):
    """Utility to convert volume values."""

    UNIT_CLASS = "volume"
    NORMALIZED_UNIT = VOLUME_CUBIC_METERS
    # Units in terms of m³
    UNIT_CONVERSION: dict[str, float] = {
        VOLUME_LITERS: 1 / _L_TO_CUBIC_METER,
        VOLUME_MILLILITERS: 1 / _ML_TO_CUBIC_METER,
        VOLUME_GALLONS: 1 / _GALLON_TO_CUBIC_METER,
        VOLUME_FLUID_OUNCE: 1 / _FLUID_OUNCE_TO_CUBIC_METER,
        VOLUME_CUBIC_METERS: 1,
        VOLUME_CUBIC_FEET: 1 / _CUBIC_FOOT_TO_CUBIC_METER,
    }
    VALID_UNITS: tuple[str, ...] = (
        VOLUME_LITERS,
        VOLUME_MILLILITERS,
        VOLUME_GALLONS,
        VOLUME_FLUID_OUNCE,
        VOLUME_CUBIC_METERS,
        VOLUME_CUBIC_FEET,
    )
