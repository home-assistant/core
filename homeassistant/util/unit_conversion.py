"""Typing Helpers for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    UnitOfArea,
    UnitOfBloodGlucoseConcentration,
    UnitOfConductivity,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfInformation,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
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

# Area constants to square meters
_CM2_TO_M2 = _CM_TO_M**2  # 1 cm² = 0.0001 m²
_MM2_TO_M2 = _MM_TO_M**2  # 1 mm² = 0.000001 m²
_KM2_TO_M2 = _KM_TO_M**2  # 1 km² = 1,000,000 m²

_IN2_TO_M2 = _IN_TO_M**2  # 1 in² = 0.00064516 m²
_FT2_TO_M2 = _FOOT_TO_M**2  # 1 ft² = 0.092903 m²
_YD2_TO_M2 = _YARD_TO_M**2  # 1 yd² = 0.836127 m²
_MI2_TO_M2 = _MILE_TO_M**2  # 1 mi² = 2,590,000 m²

_ACRE_TO_M2 = 66 * 660 * _FT2_TO_M2  # 1 acre = 4,046.86 m²
_HECTARE_TO_M2 = 100 * 100  # 1 hectare = 10,000 m²

# Duration conversion constants
_MIN_TO_SEC = 60  # 1 min = 60 seconds
_HRS_TO_MINUTES = 60  # 1 hr = 60 minutes
_HRS_TO_SECS = _HRS_TO_MINUTES * _MIN_TO_SEC  # 1 hr = 60 minutes = 3600 seconds
_DAYS_TO_SECS = 24 * _HRS_TO_SECS  # 1 day = 24 hours = 86400 seconds

# Energy conversion constants
_WH_TO_J = 3600  # 1 Wh = 3600 J
_WH_TO_CAL = _WH_TO_J / 4.184  # 1 Wh = 860.42065 cal

# Mass conversion constants
_POUND_TO_G = 453.59237
_OUNCE_TO_G = _POUND_TO_G / 16  # 16 ounces to a pound
_STONE_TO_G = _POUND_TO_G * 14  # 14 pounds to a stone

# Pressure conversion constants
_STANDARD_GRAVITY = 9.80665
_MERCURY_DENSITY = 13.5951

# Volume conversion constants
_L_TO_CUBIC_METER = 0.001  # 1 L = 0.001 m³
_ML_TO_CUBIC_METER = 0.001 * _L_TO_CUBIC_METER  # 1 mL = 0.001 L
_GALLON_TO_CUBIC_METER = 231 * pow(_IN_TO_M, 3)  # US gallon is 231 cubic inches
_FLUID_OUNCE_TO_CUBIC_METER = _GALLON_TO_CUBIC_METER / 128  # 128 fl. oz. in a US gallon
_CUBIC_FOOT_TO_CUBIC_METER = pow(_FOOT_TO_M, 3)


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    UNIT_CLASS: str
    VALID_UNITS: set[str | None]

    _UNIT_CONVERSION: dict[str | None, float]

    @classmethod
    def convert(cls, value: float, from_unit: str | None, to_unit: str | None) -> float:
        """Convert one unit of measurement to another."""
        return cls.converter_factory(from_unit, to_unit)(value)

    @classmethod
    @lru_cache
    def converter_factory(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float], float]:
        """Return a function to convert one unit of measurement to another."""
        if from_unit == to_unit:
            return lambda value: value
        from_ratio, to_ratio = cls._get_from_to_ratio(from_unit, to_unit)
        return lambda val: (val / from_ratio) * to_ratio

    @classmethod
    def _get_from_to_ratio(
        cls, from_unit: str | None, to_unit: str | None
    ) -> tuple[float, float]:
        """Get unit ratio between units of measurement."""
        unit_conversion = cls._UNIT_CONVERSION
        try:
            return unit_conversion[from_unit], unit_conversion[to_unit]
        except KeyError as err:
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(err.args[0], cls.UNIT_CLASS)
            ) from err

    @classmethod
    @lru_cache
    def converter_factory_allow_none(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float | None], float | None]:
        """Return a function to convert one unit of measurement to another which allows None."""
        if from_unit == to_unit:
            return lambda value: value
        from_ratio, to_ratio = cls._get_from_to_ratio(from_unit, to_unit)
        return lambda val: None if val is None else (val / from_ratio) * to_ratio

    @classmethod
    @lru_cache
    def get_unit_ratio(cls, from_unit: str | None, to_unit: str | None) -> float:
        """Get unit ratio between units of measurement."""
        from_ratio, to_ratio = cls._get_from_to_ratio(from_unit, to_unit)
        return from_ratio / to_ratio


class DataRateConverter(BaseUnitConverter):
    """Utility to convert data rate values."""

    UNIT_CLASS = "data_rate"
    # Units in terms of bits
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfDataRate.BITS_PER_SECOND: 1,
        UnitOfDataRate.KILOBITS_PER_SECOND: 1 / 1e3,
        UnitOfDataRate.MEGABITS_PER_SECOND: 1 / 1e6,
        UnitOfDataRate.GIGABITS_PER_SECOND: 1 / 1e9,
        UnitOfDataRate.BYTES_PER_SECOND: 1 / 8,
        UnitOfDataRate.KILOBYTES_PER_SECOND: 1 / 8e3,
        UnitOfDataRate.MEGABYTES_PER_SECOND: 1 / 8e6,
        UnitOfDataRate.GIGABYTES_PER_SECOND: 1 / 8e9,
        UnitOfDataRate.KIBIBYTES_PER_SECOND: 1 / 2**13,
        UnitOfDataRate.MEBIBYTES_PER_SECOND: 1 / 2**23,
        UnitOfDataRate.GIBIBYTES_PER_SECOND: 1 / 2**33,
    }
    VALID_UNITS = set(UnitOfDataRate)


class AreaConverter(BaseUnitConverter):
    """Utility to convert area values."""

    UNIT_CLASS = "area"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfArea.SQUARE_METERS: 1,
        UnitOfArea.SQUARE_CENTIMETERS: 1 / _CM2_TO_M2,
        UnitOfArea.SQUARE_MILLIMETERS: 1 / _MM2_TO_M2,
        UnitOfArea.SQUARE_KILOMETERS: 1 / _KM2_TO_M2,
        UnitOfArea.SQUARE_INCHES: 1 / _IN2_TO_M2,
        UnitOfArea.SQUARE_FEET: 1 / _FT2_TO_M2,
        UnitOfArea.SQUARE_YARDS: 1 / _YD2_TO_M2,
        UnitOfArea.SQUARE_MILES: 1 / _MI2_TO_M2,
        UnitOfArea.ACRES: 1 / _ACRE_TO_M2,
        UnitOfArea.HECTARES: 1 / _HECTARE_TO_M2,
    }
    VALID_UNITS = set(UnitOfArea)


class DistanceConverter(BaseUnitConverter):
    """Utility to convert distance values."""

    UNIT_CLASS = "distance"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfLength.METERS: 1,
        UnitOfLength.MILLIMETERS: 1 / _MM_TO_M,
        UnitOfLength.CENTIMETERS: 1 / _CM_TO_M,
        UnitOfLength.KILOMETERS: 1 / _KM_TO_M,
        UnitOfLength.INCHES: 1 / _IN_TO_M,
        UnitOfLength.FEET: 1 / _FOOT_TO_M,
        UnitOfLength.YARDS: 1 / _YARD_TO_M,
        UnitOfLength.MILES: 1 / _MILE_TO_M,
        UnitOfLength.NAUTICAL_MILES: 1 / _NAUTICAL_MILE_TO_M,
    }
    VALID_UNITS = {
        UnitOfLength.KILOMETERS,
        UnitOfLength.MILES,
        UnitOfLength.NAUTICAL_MILES,
        UnitOfLength.FEET,
        UnitOfLength.METERS,
        UnitOfLength.CENTIMETERS,
        UnitOfLength.MILLIMETERS,
        UnitOfLength.INCHES,
        UnitOfLength.YARDS,
    }


class BloodGlucoseConcentrationConverter(BaseUnitConverter):
    """Utility to convert blood glucose concentration values."""

    UNIT_CLASS = "blood_glucose_concentration"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER: 18,
        UnitOfBloodGlucoseConcentration.MILLIMOLE_PER_LITER: 1,
    }
    VALID_UNITS = set(UnitOfBloodGlucoseConcentration)


class ConductivityConverter(BaseUnitConverter):
    """Utility to convert electric current values."""

    UNIT_CLASS = "conductivity"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfConductivity.MICROSIEMENS_PER_CM: 1,
        UnitOfConductivity.MILLISIEMENS_PER_CM: 1e-3,
        UnitOfConductivity.SIEMENS_PER_CM: 1e-6,
    }
    VALID_UNITS = set(UnitOfConductivity)


class ElectricCurrentConverter(BaseUnitConverter):
    """Utility to convert electric current values."""

    UNIT_CLASS = "electric_current"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfElectricCurrent.AMPERE: 1,
        UnitOfElectricCurrent.MILLIAMPERE: 1e3,
    }
    VALID_UNITS = set(UnitOfElectricCurrent)


class ElectricPotentialConverter(BaseUnitConverter):
    """Utility to convert electric potential values."""

    UNIT_CLASS = "voltage"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfElectricPotential.VOLT: 1,
        UnitOfElectricPotential.MILLIVOLT: 1e3,
        UnitOfElectricPotential.MICROVOLT: 1e6,
    }
    VALID_UNITS = {
        UnitOfElectricPotential.VOLT,
        UnitOfElectricPotential.MILLIVOLT,
        UnitOfElectricPotential.MICROVOLT,
    }


class EnergyConverter(BaseUnitConverter):
    """Utility to convert energy values."""

    UNIT_CLASS = "energy"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfEnergy.JOULE: _WH_TO_J * 1e3,
        UnitOfEnergy.KILO_JOULE: _WH_TO_J,
        UnitOfEnergy.MEGA_JOULE: _WH_TO_J / 1e3,
        UnitOfEnergy.GIGA_JOULE: _WH_TO_J / 1e6,
        UnitOfEnergy.MILLIWATT_HOUR: 1e6,
        UnitOfEnergy.WATT_HOUR: 1e3,
        UnitOfEnergy.KILO_WATT_HOUR: 1,
        UnitOfEnergy.MEGA_WATT_HOUR: 1 / 1e3,
        UnitOfEnergy.GIGA_WATT_HOUR: 1 / 1e6,
        UnitOfEnergy.TERA_WATT_HOUR: 1 / 1e9,
        UnitOfEnergy.CALORIE: _WH_TO_CAL * 1e3,
        UnitOfEnergy.KILO_CALORIE: _WH_TO_CAL,
        UnitOfEnergy.MEGA_CALORIE: _WH_TO_CAL / 1e3,
        UnitOfEnergy.GIGA_CALORIE: _WH_TO_CAL / 1e6,
    }
    VALID_UNITS = set(UnitOfEnergy)


class InformationConverter(BaseUnitConverter):
    """Utility to convert information values."""

    UNIT_CLASS = "information"
    # Units in terms of bits
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfInformation.BITS: 1,
        UnitOfInformation.KILOBITS: 1 / 1e3,
        UnitOfInformation.MEGABITS: 1 / 1e6,
        UnitOfInformation.GIGABITS: 1 / 1e9,
        UnitOfInformation.BYTES: 1 / 8,
        UnitOfInformation.KILOBYTES: 1 / 8e3,
        UnitOfInformation.MEGABYTES: 1 / 8e6,
        UnitOfInformation.GIGABYTES: 1 / 8e9,
        UnitOfInformation.TERABYTES: 1 / 8e12,
        UnitOfInformation.PETABYTES: 1 / 8e15,
        UnitOfInformation.EXABYTES: 1 / 8e18,
        UnitOfInformation.ZETTABYTES: 1 / 8e21,
        UnitOfInformation.YOTTABYTES: 1 / 8e24,
        UnitOfInformation.KIBIBYTES: 1 / 2**13,
        UnitOfInformation.MEBIBYTES: 1 / 2**23,
        UnitOfInformation.GIBIBYTES: 1 / 2**33,
        UnitOfInformation.TEBIBYTES: 1 / 2**43,
        UnitOfInformation.PEBIBYTES: 1 / 2**53,
        UnitOfInformation.EXBIBYTES: 1 / 2**63,
        UnitOfInformation.ZEBIBYTES: 1 / 2**73,
        UnitOfInformation.YOBIBYTES: 1 / 2**83,
    }
    VALID_UNITS = set(UnitOfInformation)


class MassConverter(BaseUnitConverter):
    """Utility to convert mass values."""

    UNIT_CLASS = "mass"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfMass.MICROGRAMS: 1 * 1000 * 1000,
        UnitOfMass.MILLIGRAMS: 1 * 1000,
        UnitOfMass.GRAMS: 1,
        UnitOfMass.KILOGRAMS: 1 / 1000,
        UnitOfMass.OUNCES: 1 / _OUNCE_TO_G,
        UnitOfMass.POUNDS: 1 / _POUND_TO_G,
        UnitOfMass.STONES: 1 / _STONE_TO_G,
    }
    VALID_UNITS = {
        UnitOfMass.GRAMS,
        UnitOfMass.KILOGRAMS,
        UnitOfMass.MILLIGRAMS,
        UnitOfMass.MICROGRAMS,
        UnitOfMass.OUNCES,
        UnitOfMass.POUNDS,
        UnitOfMass.STONES,
    }


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    UNIT_CLASS = "power"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfPower.MILLIWATT: 1 * 1000,
        UnitOfPower.WATT: 1,
        UnitOfPower.KILO_WATT: 1 / 1000,
        UnitOfPower.MEGA_WATT: 1 / 1e6,
        UnitOfPower.GIGA_WATT: 1 / 1e9,
        UnitOfPower.TERA_WATT: 1 / 1e12,
    }
    VALID_UNITS = {
        UnitOfPower.MILLIWATT,
        UnitOfPower.WATT,
        UnitOfPower.KILO_WATT,
        UnitOfPower.MEGA_WATT,
        UnitOfPower.GIGA_WATT,
        UnitOfPower.TERA_WATT,
    }


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    UNIT_CLASS = "pressure"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfPressure.PA: 1,
        UnitOfPressure.HPA: 1 / 100,
        UnitOfPressure.KPA: 1 / 1000,
        UnitOfPressure.BAR: 1 / 100000,
        UnitOfPressure.CBAR: 1 / 1000,
        UnitOfPressure.MBAR: 1 / 100,
        UnitOfPressure.INHG: 1
        / (_IN_TO_M * 1000 * _STANDARD_GRAVITY * _MERCURY_DENSITY),
        UnitOfPressure.PSI: 1 / 6894.757,
        UnitOfPressure.MMHG: 1
        / (_MM_TO_M * 1000 * _STANDARD_GRAVITY * _MERCURY_DENSITY),
    }
    VALID_UNITS = {
        UnitOfPressure.PA,
        UnitOfPressure.HPA,
        UnitOfPressure.KPA,
        UnitOfPressure.BAR,
        UnitOfPressure.CBAR,
        UnitOfPressure.MBAR,
        UnitOfPressure.INHG,
        UnitOfPressure.PSI,
        UnitOfPressure.MMHG,
    }


class SpeedConverter(BaseUnitConverter):
    """Utility to convert speed values."""

    UNIT_CLASS = "speed"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfVolumetricFlux.INCHES_PER_DAY: _DAYS_TO_SECS / _IN_TO_M,
        UnitOfVolumetricFlux.INCHES_PER_HOUR: _HRS_TO_SECS / _IN_TO_M,
        UnitOfVolumetricFlux.MILLIMETERS_PER_DAY: _DAYS_TO_SECS / _MM_TO_M,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR: _HRS_TO_SECS / _MM_TO_M,
        UnitOfSpeed.FEET_PER_SECOND: 1 / _FOOT_TO_M,
        UnitOfSpeed.INCHES_PER_SECOND: 1 / _IN_TO_M,
        UnitOfSpeed.KILOMETERS_PER_HOUR: _HRS_TO_SECS / _KM_TO_M,
        UnitOfSpeed.KNOTS: _HRS_TO_SECS / _NAUTICAL_MILE_TO_M,
        UnitOfSpeed.METERS_PER_SECOND: 1,
        UnitOfSpeed.MILLIMETERS_PER_SECOND: 1 / _MM_TO_M,
        UnitOfSpeed.MILES_PER_HOUR: _HRS_TO_SECS / _MILE_TO_M,
        UnitOfSpeed.BEAUFORT: 1,
    }
    VALID_UNITS = {
        UnitOfVolumetricFlux.INCHES_PER_DAY,
        UnitOfVolumetricFlux.INCHES_PER_HOUR,
        UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        UnitOfSpeed.INCHES_PER_SECOND,
        UnitOfSpeed.FEET_PER_SECOND,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        UnitOfSpeed.KNOTS,
        UnitOfSpeed.METERS_PER_SECOND,
        UnitOfSpeed.MILES_PER_HOUR,
        UnitOfSpeed.MILLIMETERS_PER_SECOND,
        UnitOfSpeed.BEAUFORT,
    }

    @classmethod
    @lru_cache
    def converter_factory(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float], float]:
        """Return a function to convert a speed from one unit to another."""
        if from_unit == to_unit:
            # Return a function that does nothing. This is not
            # in _converter_factory because we do not want to wrap
            # it with the None check in converter_factory_allow_none.
            return lambda value: value

        return cls._converter_factory(from_unit, to_unit)

    @classmethod
    @lru_cache
    def converter_factory_allow_none(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float | None], float | None]:
        """Return a function to convert a speed from one unit to another which allows None."""
        if from_unit == to_unit:
            # Return a function that does nothing. This is not
            # in _converter_factory because we do not want to wrap
            # it with the None check in this case.
            return lambda value: value

        convert = cls._converter_factory(from_unit, to_unit)
        return lambda value: None if value is None else convert(value)

    @classmethod
    def _converter_factory(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float], float]:
        """Convert a speed from one unit to another, eg. 14m/s will return 7Bft."""
        # We cannot use the implementation from BaseUnitConverter here because the
        # Beaufort scale is not a constant value to divide or multiply with.
        if (
            from_unit not in SpeedConverter.VALID_UNITS
            or to_unit not in SpeedConverter.VALID_UNITS
        ):
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )

        if from_unit == UnitOfSpeed.BEAUFORT:
            to_ratio = cls._UNIT_CONVERSION[to_unit]
            return lambda val: cls._beaufort_to_ms(val) * to_ratio
        if to_unit == UnitOfSpeed.BEAUFORT:
            from_ratio = cls._UNIT_CONVERSION[from_unit]
            return lambda val: cls._ms_to_beaufort(val / from_ratio)

        from_ratio, to_ratio = cls._get_from_to_ratio(from_unit, to_unit)
        return lambda val: (val / from_ratio) * to_ratio

    @classmethod
    def _ms_to_beaufort(cls, ms: float) -> float:
        """Convert a speed in m/s to Beaufort."""
        return float(round(((ms / 0.836) ** 2) ** (1 / 3)))

    @classmethod
    def _beaufort_to_ms(cls, beaufort: float) -> float:
        """Convert a speed in Beaufort to m/s."""
        return float(0.836 * beaufort ** (3 / 2))


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    UNIT_CLASS = "temperature"
    VALID_UNITS = {
        UnitOfTemperature.CELSIUS,
        UnitOfTemperature.FAHRENHEIT,
        UnitOfTemperature.KELVIN,
    }
    _UNIT_CONVERSION = {
        UnitOfTemperature.CELSIUS: 1.0,
        UnitOfTemperature.FAHRENHEIT: 1.8,
        UnitOfTemperature.KELVIN: 1.0,
    }

    @classmethod
    @lru_cache
    def converter_factory(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float], float]:
        """Return a function to convert a temperature from one unit to another."""
        if from_unit == to_unit:
            # Return a function that does nothing. This is not
            # in _converter_factory because we do not want to wrap
            # it with the None check in converter_factory_allow_none.
            return lambda value: value

        return cls._converter_factory(from_unit, to_unit)

    @classmethod
    @lru_cache
    def converter_factory_allow_none(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float | None], float | None]:
        """Return a function to convert a temperature from one unit to another which allows None."""
        if from_unit == to_unit:
            # Return a function that does nothing. This is not
            # in _converter_factory because we do not want to wrap
            # it with the None check in this case.
            return lambda value: value
        convert = cls._converter_factory(from_unit, to_unit)
        return lambda value: None if value is None else convert(value)

    @classmethod
    def _converter_factory(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float], float]:
        """Convert a temperature from one unit to another.

        eg. 10°C will return 50°F

        For converting an interval between two temperatures, please use
        `convert_interval` instead.
        """
        # We cannot use the implementation from BaseUnitConverter here because the
        # temperature units do not use the same floor: 0°C, 0°F and 0K do not align
        if from_unit == UnitOfTemperature.CELSIUS:
            if to_unit == UnitOfTemperature.FAHRENHEIT:
                return cls._celsius_to_fahrenheit
            if to_unit == UnitOfTemperature.KELVIN:
                return cls._celsius_to_kelvin
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )

        if from_unit == UnitOfTemperature.FAHRENHEIT:
            if to_unit == UnitOfTemperature.CELSIUS:
                return cls._fahrenheit_to_celsius
            if to_unit == UnitOfTemperature.KELVIN:
                return cls._fahrenheit_to_kelvin
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, cls.UNIT_CLASS)
            )

        if from_unit == UnitOfTemperature.KELVIN:
            if to_unit == UnitOfTemperature.CELSIUS:
                return cls._kelvin_to_celsius
            if to_unit == UnitOfTemperature.FAHRENHEIT:
                return cls._kelvin_to_fahrenheit
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
        return super().converter_factory(from_unit, to_unit)(interval)

    @classmethod
    def _kelvin_to_fahrenheit(cls, kelvin: float) -> float:
        """Convert a temperature in Kelvin to Fahrenheit."""
        return (kelvin - 273.15) * 1.8 + 32.0

    @classmethod
    def _fahrenheit_to_kelvin(cls, fahrenheit: float) -> float:
        """Convert a temperature in Fahrenheit to Kelvin."""
        return 273.15 + ((fahrenheit - 32.0) / 1.8)

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


class UnitlessRatioConverter(BaseUnitConverter):
    """Utility to convert unitless ratios."""

    UNIT_CLASS = "unitless"
    _UNIT_CONVERSION: dict[str | None, float] = {
        None: 1,
        CONCENTRATION_PARTS_PER_BILLION: 1000000000,
        CONCENTRATION_PARTS_PER_MILLION: 1000000,
        PERCENTAGE: 100,
    }
    VALID_UNITS = {
        None,
        PERCENTAGE,
    }


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    UNIT_CLASS = "volume"
    # Units in terms of m³
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfVolume.LITERS: 1 / _L_TO_CUBIC_METER,
        UnitOfVolume.MILLILITERS: 1 / _ML_TO_CUBIC_METER,
        UnitOfVolume.GALLONS: 1 / _GALLON_TO_CUBIC_METER,
        UnitOfVolume.FLUID_OUNCES: 1 / _FLUID_OUNCE_TO_CUBIC_METER,
        UnitOfVolume.CUBIC_METERS: 1,
        UnitOfVolume.CUBIC_FEET: 1 / _CUBIC_FOOT_TO_CUBIC_METER,
        UnitOfVolume.CENTUM_CUBIC_FEET: 1 / (100 * _CUBIC_FOOT_TO_CUBIC_METER),
    }
    VALID_UNITS = {
        UnitOfVolume.LITERS,
        UnitOfVolume.MILLILITERS,
        UnitOfVolume.GALLONS,
        UnitOfVolume.FLUID_OUNCES,
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.CENTUM_CUBIC_FEET,
    }


class VolumeFlowRateConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    UNIT_CLASS = "volume_flow_rate"
    # Units in terms of m³/h
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR: 1,
        UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE: 1
        / (_HRS_TO_MINUTES * _CUBIC_FOOT_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.LITERS_PER_MINUTE: 1
        / (_HRS_TO_MINUTES * _L_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.GALLONS_PER_MINUTE: 1
        / (_HRS_TO_MINUTES * _GALLON_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.MILLILITERS_PER_SECOND: 1
        / (_HRS_TO_SECS * _ML_TO_CUBIC_METER),
    }
    VALID_UNITS = {
        UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        UnitOfVolumeFlowRate.MILLILITERS_PER_SECOND,
    }


class DurationConverter(BaseUnitConverter):
    """Utility to convert duration values."""

    UNIT_CLASS = "duration"
    _UNIT_CONVERSION: dict[str | None, float] = {
        UnitOfTime.MICROSECONDS: 1000000,
        UnitOfTime.MILLISECONDS: 1000,
        UnitOfTime.SECONDS: 1,
        UnitOfTime.MINUTES: 1 / _MIN_TO_SEC,
        UnitOfTime.HOURS: 1 / _HRS_TO_SECS,
        UnitOfTime.DAYS: 1 / _DAYS_TO_SECS,
        UnitOfTime.WEEKS: 1 / (7 * _DAYS_TO_SECS),
    }
    VALID_UNITS = {
        UnitOfTime.MICROSECONDS,
        UnitOfTime.MILLISECONDS,
        UnitOfTime.SECONDS,
        UnitOfTime.MINUTES,
        UnitOfTime.HOURS,
        UnitOfTime.DAYS,
        UnitOfTime.WEEKS,
    }
