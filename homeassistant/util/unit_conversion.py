"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
    MASS_GRAMS,
    MASS_KILOGRAMS,
    MASS_MICROGRAMS,
    MASS_MILLIGRAMS,
    MASS_OUNCES,
    MASS_POUNDS,
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
    SPEED_FEET_PER_SECOND,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
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
from homeassistant.exceptions import HomeAssistantError

# Distance conversion constants
_MM_TO_M = 0.001  # 1 mm = 0.001 m
_CM_TO_M = 0.01  # 1 cm = 0.01 m
_KM_TO_M = 1000  # 1 km = 1000 m

_IN_TO_M = 0.0254  # 1 inch = 0.0254 m
_FOOT_TO_M = _IN_TO_M * 12  # 12 inches = 1 foot (0.3048 m)
_YARD_TO_M = _FOOT_TO_M * 3  # 3 feet = 1 yard (0.9144 m)
_MILE_TO_M = _YARD_TO_M * 1760  # 1760 yard = 1 mile (1609.344 m)

_NAUTICAL_MILE_TO_M = 1852  # 1 nautical mile = 1852 m

# Duration conversion constants
_HRS_TO_SECS = 60 * 60  # 1 hr = 3600 seconds
_DAYS_TO_SECS = 24 * _HRS_TO_SECS  # 1 day = 24 hours = 86400 seconds

# Mass conversion constants
_POUND_TO_G = 453.59237
_OUNCE_TO_G = _POUND_TO_G / 16

# Volume conversion constants
_L_TO_CUBIC_METER = 0.001  # 1 L = 0.001 m³
_ML_TO_CUBIC_METER = 0.001 * _L_TO_CUBIC_METER  # 1 mL = 0.001 L
_GALLON_TO_CUBIC_METER = 231 * pow(_IN_TO_M, 3)  # US gallon is 231 cubic inches
_FLUID_OUNCE_TO_CUBIC_METER = _GALLON_TO_CUBIC_METER / 128  # 128 fl. oz. in a US gallon
_CUBIC_FOOT_TO_CUBIC_METER = pow(_FOOT_TO_M, 3)


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    UNIT_CLASS: str
    NORMALIZED_UNIT: str
    VALID_UNITS: set[str]

    _UNIT_CONVERSION: dict[str, float]

    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""
        if from_unit == to_unit:
            return value

        try:
            from_ratio = cls._UNIT_CONVERSION[from_unit]
        except KeyError as err:
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, cls.UNIT_CLASS)
            ) from err

        try:
            to_ratio = cls._UNIT_CONVERSION[to_unit]
        except KeyError as err:
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            ) from err

        new_value = value / from_ratio
        return new_value * to_ratio

    @classmethod
    def get_unit_ratio(cls, from_unit: str, to_unit: str) -> float:
        """Get unit ratio between units of measurement."""
        return cls._UNIT_CONVERSION[from_unit] / cls._UNIT_CONVERSION[to_unit]


class DistanceConverter(BaseUnitConverter):
    """Utility to convert distance values."""

    UNIT_CLASS = "distance"
    NORMALIZED_UNIT = LENGTH_METERS
    _UNIT_CONVERSION: dict[str, float] = {
        LENGTH_METERS: 1,
        LENGTH_MILLIMETERS: 1 / _MM_TO_M,
        LENGTH_CENTIMETERS: 1 / _CM_TO_M,
        LENGTH_KILOMETERS: 1 / _KM_TO_M,
        LENGTH_INCHES: 1 / _IN_TO_M,
        LENGTH_FEET: 1 / _FOOT_TO_M,
        LENGTH_YARD: 1 / _YARD_TO_M,
        LENGTH_MILES: 1 / _MILE_TO_M,
    }
    VALID_UNITS = {
        LENGTH_KILOMETERS,
        LENGTH_MILES,
        LENGTH_FEET,
        LENGTH_METERS,
        LENGTH_CENTIMETERS,
        LENGTH_MILLIMETERS,
        LENGTH_INCHES,
        LENGTH_YARD,
    }


class EnergyConverter(BaseUnitConverter):
    """Utility to convert energy values."""

    UNIT_CLASS = "energy"
    NORMALIZED_UNIT = ENERGY_KILO_WATT_HOUR
    _UNIT_CONVERSION: dict[str, float] = {
        ENERGY_WATT_HOUR: 1 * 1000,
        ENERGY_KILO_WATT_HOUR: 1,
        ENERGY_MEGA_WATT_HOUR: 1 / 1000,
    }
    VALID_UNITS = {
        ENERGY_WATT_HOUR,
        ENERGY_KILO_WATT_HOUR,
        ENERGY_MEGA_WATT_HOUR,
    }


class MassConverter(BaseUnitConverter):
    """Utility to convert mass values."""

    UNIT_CLASS = "mass"
    NORMALIZED_UNIT = MASS_GRAMS
    _UNIT_CONVERSION: dict[str, float] = {
        MASS_MICROGRAMS: 1 * 1000 * 1000,
        MASS_MILLIGRAMS: 1 * 1000,
        MASS_GRAMS: 1,
        MASS_KILOGRAMS: 1 / 1000,
        MASS_OUNCES: 1 / _OUNCE_TO_G,
        MASS_POUNDS: 1 / _POUND_TO_G,
    }
    VALID_UNITS = {
        MASS_GRAMS,
        MASS_KILOGRAMS,
        MASS_MILLIGRAMS,
        MASS_MICROGRAMS,
        MASS_OUNCES,
        MASS_POUNDS,
    }


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    UNIT_CLASS = "power"
    NORMALIZED_UNIT = POWER_WATT
    _UNIT_CONVERSION: dict[str, float] = {
        POWER_WATT: 1,
        POWER_KILO_WATT: 1 / 1000,
    }
    VALID_UNITS = {
        POWER_WATT,
        POWER_KILO_WATT,
    }


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    UNIT_CLASS = "pressure"
    NORMALIZED_UNIT = PRESSURE_PA
    _UNIT_CONVERSION: dict[str, float] = {
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
    VALID_UNITS = {
        PRESSURE_PA,
        PRESSURE_HPA,
        PRESSURE_KPA,
        PRESSURE_BAR,
        PRESSURE_CBAR,
        PRESSURE_MBAR,
        PRESSURE_INHG,
        PRESSURE_PSI,
        PRESSURE_MMHG,
    }


class SpeedConverter(BaseUnitConverter):
    """Utility to convert speed values."""

    UNIT_CLASS = "speed"
    NORMALIZED_UNIT = SPEED_METERS_PER_SECOND
    _UNIT_CONVERSION: dict[str, float] = {
        SPEED_FEET_PER_SECOND: 1 / _FOOT_TO_M,
        SPEED_INCHES_PER_DAY: _DAYS_TO_SECS / _IN_TO_M,
        SPEED_INCHES_PER_HOUR: _HRS_TO_SECS / _IN_TO_M,
        SPEED_KILOMETERS_PER_HOUR: _HRS_TO_SECS / _KM_TO_M,
        SPEED_KNOTS: _HRS_TO_SECS / _NAUTICAL_MILE_TO_M,
        SPEED_METERS_PER_SECOND: 1,
        SPEED_MILES_PER_HOUR: _HRS_TO_SECS / _MILE_TO_M,
        SPEED_MILLIMETERS_PER_DAY: _DAYS_TO_SECS / _MM_TO_M,
    }
    VALID_UNITS = {
        SPEED_FEET_PER_SECOND,
        SPEED_INCHES_PER_DAY,
        SPEED_INCHES_PER_HOUR,
        SPEED_KILOMETERS_PER_HOUR,
        SPEED_KNOTS,
        SPEED_METERS_PER_SECOND,
        SPEED_MILES_PER_HOUR,
        SPEED_MILLIMETERS_PER_DAY,
    }


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    UNIT_CLASS = "temperature"
    NORMALIZED_UNIT = TEMP_CELSIUS
    VALID_UNITS = {
        TEMP_CELSIUS,
        TEMP_FAHRENHEIT,
        TEMP_KELVIN,
    }
    _UNIT_CONVERSION = {
        TEMP_CELSIUS: 1.0,
        TEMP_FAHRENHEIT: 1.8,
        TEMP_KELVIN: 1.0,
    }

    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert a temperature from one unit to another.

        eg. 10°C will return 50°F

        For converting an interval between two temperatures, please use
        `convert_interval` instead.
        """
        # We cannot use the implementation from BaseUnitConverter here because the temperature
        # units do not use the same floor: 0°C, 0°F and 0K do not align
        if from_unit == to_unit:
            return value

        if from_unit == TEMP_CELSIUS:
            if to_unit == TEMP_FAHRENHEIT:
                return cls._celsius_to_fahrenheit(value)
            if to_unit == TEMP_KELVIN:
                return cls._celsius_to_kelvin(value)
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )

        if from_unit == TEMP_FAHRENHEIT:
            if to_unit == TEMP_CELSIUS:
                return cls._fahrenheit_to_celsius(value)
            if to_unit == TEMP_KELVIN:
                return cls._celsius_to_kelvin(cls._fahrenheit_to_celsius(value))
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )

        if from_unit == TEMP_KELVIN:
            if to_unit == TEMP_CELSIUS:
                return cls._kelvin_to_celsius(value)
            if to_unit == TEMP_FAHRENHEIT:
                return cls._celsius_to_fahrenheit(cls._kelvin_to_celsius(value))
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )
        raise HomeAssistantError(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, cls.UNIT_CLASS)
        )

    @classmethod
    def convert_interval(cls, interval: float, from_unit: str, to_unit: str) -> float:
        """Convert a temperature interval from one unit to another.

        eg. a 10°C interval (10°C to 20°C) will return a 18°F (50°F to 68°F) interval

        For converting a temperature value, please use `convert` as this method
        skips floor adjustment.
        """
        # We use BaseUnitConverter implementation here because we are only interested
        # in the ratio between the units.
        return super().convert(interval, from_unit, to_unit)

    @classmethod
    def _fahrenheit_to_celsius(cls, fahrenheit: float) -> float:
        """Convert a temperature in Fahrenheit to Celsius."""
        return (fahrenheit - 32.0) / 1.8

    @classmethod
    def _kelvin_to_celsius(cls, kelvin: float) -> float:
        """Convert a temperature in Kelvin to Celsius."""
        return kelvin - 273.15

    @classmethod
    def _celsius_to_fahrenheit(cls, celsius: float) -> float:
        """Convert a temperature in Celsius to Fahrenheit."""
        return celsius * 1.8 + 32.0

    @classmethod
    def _celsius_to_kelvin(cls, celsius: float) -> float:
        """Convert a temperature in Celsius to Kelvin."""
        return celsius + 273.15


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    UNIT_CLASS = "volume"
    NORMALIZED_UNIT = VOLUME_CUBIC_METERS
    # Units in terms of m³
    _UNIT_CONVERSION: dict[str, float] = {
        VOLUME_LITERS: 1 / _L_TO_CUBIC_METER,
        VOLUME_MILLILITERS: 1 / _ML_TO_CUBIC_METER,
        VOLUME_GALLONS: 1 / _GALLON_TO_CUBIC_METER,
        VOLUME_FLUID_OUNCE: 1 / _FLUID_OUNCE_TO_CUBIC_METER,
        VOLUME_CUBIC_METERS: 1,
        VOLUME_CUBIC_FEET: 1 / _CUBIC_FOOT_TO_CUBIC_METER,
    }
    VALID_UNITS = {
        VOLUME_LITERS,
        VOLUME_MILLILITERS,
        VOLUME_GALLONS,
        VOLUME_FLUID_OUNCE,
        VOLUME_CUBIC_METERS,
        VOLUME_CUBIC_FEET,
    }
