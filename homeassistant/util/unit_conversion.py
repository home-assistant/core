"""Typing Helpers for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from functools import lru_cache
from math import floor, log10

from homeassistant.const import (
    PERCENTAGE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    UnitOfApparentPower,
    UnitOfArea,
    UnitOfBloodGlucoseConcentration,
    UnitOfConcentration,
    UnitOfConductivity,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfInformation,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.deprecation import deprecated_function

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
_DAYS_TO_HRS = 24  # 1 day = 24 hours
_DAYS_TO_SECS = _DAYS_TO_HRS * _HRS_TO_SECS  # 1 day = 24 hours = 86400 seconds

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
_INH2O_TO_PA = 249.0889083333348  # 1 inH₂O = 249.0889083333348 Pa at 4°C

# Volume conversion constants
_L_TO_CUBIC_METER = 0.001  # 1 L = 0.001 m³
_ML_TO_CUBIC_METER = 0.001 * _L_TO_CUBIC_METER  # 1 mL = 0.001 L
_GALLON_TO_CUBIC_METER = 231 * pow(_IN_TO_M, 3)  # US gallon is 231 cubic inches
_FLUID_OUNCE_TO_CUBIC_METER = _GALLON_TO_CUBIC_METER / 128  # 128 fl. oz. in a US gallon
_CUBIC_FOOT_TO_CUBIC_METER = pow(_FOOT_TO_M, 3)

# Gas concentration conversion constants
_IDEAL_GAS_CONSTANT = 8.31446261815324  # m3⋅Pa⋅K⁻¹⋅mol⁻¹
# Ambient constants based on European Commission recommendations (20 °C and 1013mb)
_AMBIENT_TEMPERATURE = 293.15  # K (20 °C)
_AMBIENT_PRESSURE = 101325  # Pa (1 atm)
_AMBIENT_IDEAL_GAS_MOLAR_VOLUME = (  # m3⋅mol⁻¹
    _IDEAL_GAS_CONSTANT * _AMBIENT_TEMPERATURE / _AMBIENT_PRESSURE
)
# Molar masses in g⋅mol⁻¹
_CARBON_MONOXIDE_MOLAR_MASS = 28.01
_GLUCOSE_MOLAR_MASS = 180.16
_NITROGEN_DIOXIDE_MOLAR_MASS = 46.0055
_NITROGEN_MONOXIDE_MOLAR_MASS = 30.0061
_OZONE_MOLAR_MASS = 48.00
_SULPHUR_DIOXIDE_MOLAR_MASS = 64.066


# Possible unit conversion operations from JSON file
# **important** any changes made to the operations here must also be applied in the frontend
class UnitConvertOpType(StrEnum):
    """Unit conversion operations."""

    SCALE = "scale"  # Multiply by a scale factor (factor != 0)
    OFFSET = "offset"  # Add a value to (offset is numeeric)
    POWER = "power"  # Raise to the power (power != 0)
    ROUND = "round"  # Round to integer (argument unused). Applies only when converting to a unit.


# Description of a conversion operation - type and factor
type UnitConvertOpInfo = tuple[UnitConvertOpType, float]


# When determining unit ratios, offset operations are not applicable
def _is_ratio_op(opInfo: UnitConvertOpInfo) -> bool:
    (op, _unused) = opInfo
    return op != UnitConvertOpType.OFFSET


# Maps of operation info to executable functions, in both the from and to directions.
type UnitConvertOpFn = Callable[[float, float], float]
type UnitConvertOp = tuple[UnitConvertOpFn, float]

_UNIT_CONVERT_FROM_OP: dict[UnitConvertOpType, UnitConvertOpFn] = {
    UnitConvertOpType.SCALE: (lambda val, scale: val / scale),
    UnitConvertOpType.OFFSET: (lambda val, offset: val - offset),
    UnitConvertOpType.POWER: (lambda val, power: val ** (1 / power)),
    UnitConvertOpType.ROUND: (lambda val, unused: val),  # Unused when converting from
}
_UNIT_CONVERT_TO_OP: dict[UnitConvertOpType, UnitConvertOpFn] = {
    UnitConvertOpType.SCALE: (lambda val, scale: val * scale),
    UnitConvertOpType.OFFSET: (lambda val, offset: val + offset),
    UnitConvertOpType.POWER: (lambda val, power: val**power),
    UnitConvertOpType.ROUND: (lambda val, unused: round(val)),
}


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    UNIT_CLASS: str
    BASE_UNIT: str | None
    VALID_UNITS: set[str | None]

    _UNIT_INVERSES: set[str | None] = set()
    _UNIT_CONVERSION: dict[str | None, list[UnitConvertOpInfo] | float]

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
            return lambda val: val
        convert_ops = cls._get_from_to_ops(from_unit, to_unit)
        return lambda val: BaseUnitConverter._convert_fn(val, convert_ops)

    @classmethod
    @lru_cache
    def converter_factory_allow_none(
        cls, from_unit: str | None, to_unit: str | None
    ) -> Callable[[float | None], float | None]:
        """Return a function to convert one unit of measurement to another which allows None."""
        if from_unit == to_unit:
            return lambda val: val
        convert_ops = cls._get_from_to_ops(from_unit, to_unit)
        return lambda val: BaseUnitConverter._convert_allow_none_fn(val, convert_ops)

    @classmethod
    @lru_cache
    def get_unit_ratio(cls, from_unit: str | None, to_unit: str | None) -> float:
        """Get unit ratio between units of measurement."""
        if from_unit == to_unit:
            return 1
        convert_ops = cls._get_from_to_ops(to_unit, from_unit, True)
        return BaseUnitConverter._convert_fn(1, convert_ops)

    @classmethod
    @lru_cache
    def get_unit_floored_log_ratio(
        cls, from_unit: str | None, to_unit: str | None
    ) -> float:
        """Get floored base10 log ratio between units of measurement."""
        ratio = cls.get_unit_ratio(from_unit, to_unit)
        return floor(max(0, log10(ratio)))

    @classmethod
    @lru_cache
    def _get_inverse_op(
        cls, from_unit: str | None, to_unit: str | None
    ) -> list[UnitConvertOpInfo]:
        """Return inverse operation if units are inverses."""
        return (
            [(UnitConvertOpType.POWER, -1)]
            if (from_unit in cls._UNIT_INVERSES) != (to_unit in cls._UNIT_INVERSES)
            else []
        )

    @classmethod
    def _get_from_to_ops(
        cls, from_unit: str | None, to_unit: str | None, for_ratio: bool = False
    ) -> list[UnitConvertOp]:
        """Get operations to convert between units of measurement."""
        from_op_info = cls._get_ops(from_unit, for_ratio)
        to_op_info = cls._get_ops(to_unit, for_ratio)
        from_op = list(map(BaseUnitConverter._map_from_op, from_op_info))
        from_op.reverse()
        to_op = list(
            map(
                BaseUnitConverter._map_to_op,
                [*cls._get_inverse_op(from_unit, to_unit), *to_op_info],
            )
        )
        return [*from_op, *to_op]

    @classmethod
    def _get_ops(cls, unit: str | None, for_ratio: bool) -> list[UnitConvertOpInfo]:
        if unit == cls.BASE_UNIT:
            return []  # Don't have any operations to perform if unit is already the base unit.
        try:
            ops = cls._UNIT_CONVERSION[unit]
        except KeyError as err:
            raise HomeAssistantError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(err.args[0], cls.UNIT_CLASS)
            ) from err
        if not isinstance(ops, list):
            ops = [(UnitConvertOpType.SCALE, ops)]
        return ops if not for_ratio else list(filter(_is_ratio_op, ops))

    @staticmethod
    def _map_from_op(opInfo: UnitConvertOpInfo) -> UnitConvertOp:
        """Maps from operation info to converter function."""
        (opName, factor) = opInfo
        return (_UNIT_CONVERT_FROM_OP[opName], factor)

    @staticmethod
    def _map_to_op(opInfo: UnitConvertOpInfo) -> UnitConvertOp:
        """Maps to operation info to converter function."""
        (opName, factor) = opInfo
        return (_UNIT_CONVERT_TO_OP[opName], factor)

    @staticmethod
    def _convert_fn(val: float, convert_ops: list[UnitConvertOp]) -> float:
        """Execute a list of conversion operations one by one."""
        for op, factor in convert_ops:
            val = op(val, factor)
        return val

    @staticmethod
    def _convert_allow_none_fn(
        val: float | None, convert_ops: list[UnitConvertOp]
    ) -> float | None:
        """Execute a list of conversion operations one by one."""
        for op, factor in convert_ops:
            if val is None:
                break
            try:
                val = op(val, factor)
            except ZeroDivisionError:
                val = None  # On math failure treat result as None
        return val


class ApparentPowerConverter(BaseUnitConverter):
    """Utility to convert apparent power values."""

    UNIT_CLASS = "apparent_power"
    BASE_UNIT = UnitOfApparentPower.VOLT_AMPERE
    VALID_UNITS = set(UnitOfApparentPower)
    _UNIT_CONVERSION = {
        UnitOfApparentPower.MILLIVOLT_AMPERE: 1 * 1000,
        UnitOfApparentPower.VOLT_AMPERE: 1,
        UnitOfApparentPower.KILO_VOLT_AMPERE: 1 / 1000,
    }


class AreaConverter(BaseUnitConverter):
    """Utility to convert area values."""

    UNIT_CLASS = "area"
    BASE_UNIT = UnitOfArea.SQUARE_METERS
    VALID_UNITS = set(UnitOfArea)
    _UNIT_CONVERSION = {
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


class BloodGlucoseConcentrationConverter(BaseUnitConverter):
    """Utility to convert blood glucose concentration values."""

    UNIT_CLASS = "blood_glucose_concentration"
    BASE_UNIT = UnitOfBloodGlucoseConcentration.MILLIMOLE_PER_LITER
    VALID_UNITS = set(UnitOfBloodGlucoseConcentration)
    _UNIT_CONVERSION = {
        UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER: (
            _GLUCOSE_MOLAR_MASS / 10
        ),
        UnitOfBloodGlucoseConcentration.MILLIMOLE_PER_LITER: 1,
    }


class CarbonMonoxideConcentrationConverter(BaseUnitConverter):
    """Convert carbon monoxide ratio to mass per volume.

    Using ambient temperature of 20°C and pressure of 1 ATM.
    """

    UNIT_CLASS = "carbon_monoxide"
    BASE_UNIT = UnitOfConcentration.PARTS_PER_BILLION
    VALID_UNITS = {
        UnitOfConcentration.PARTS_PER_BILLION,
        UnitOfConcentration.PARTS_PER_MILLION,
        UnitOfConcentration.MILLIGRAMS_PER_CUBIC_METER,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER,
    }
    _UNIT_CONVERSION = {
        UnitOfConcentration.PARTS_PER_BILLION: 1,
        UnitOfConcentration.PARTS_PER_MILLION: 1e-3,
        UnitOfConcentration.MILLIGRAMS_PER_CUBIC_METER: (
            _CARBON_MONOXIDE_MOLAR_MASS / _AMBIENT_IDEAL_GAS_MOLAR_VOLUME * 1e-6
        ),
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER: (
            _CARBON_MONOXIDE_MOLAR_MASS / _AMBIENT_IDEAL_GAS_MOLAR_VOLUME * 1e-3
        ),
    }


class ConductivityConverter(BaseUnitConverter):
    """Utility to convert electric current values."""

    UNIT_CLASS = "conductivity"
    BASE_UNIT = UnitOfConductivity.MICROSIEMENS_PER_CM
    VALID_UNITS = set(UnitOfConductivity)
    _UNIT_CONVERSION = {
        UnitOfConductivity.MICROSIEMENS_PER_CM: 1,
        UnitOfConductivity.MILLISIEMENS_PER_CM: 1e-3,
        UnitOfConductivity.SIEMENS_PER_CM: 1e-6,
    }


class DataRateConverter(BaseUnitConverter):
    """Utility to convert data rate values."""

    UNIT_CLASS = "data_rate"
    BASE_UNIT = UnitOfDataRate.BITS_PER_SECOND
    VALID_UNITS = set(UnitOfDataRate)
    _UNIT_CONVERSION = {
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


class DistanceConverter(BaseUnitConverter):
    """Utility to convert distance values."""

    UNIT_CLASS = "distance"
    BASE_UNIT = UnitOfLength.METERS
    VALID_UNITS = set(UnitOfLength)
    _UNIT_CONVERSION = {
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


class DurationConverter(BaseUnitConverter):
    """Utility to convert duration values."""

    UNIT_CLASS = "duration"
    BASE_UNIT = UnitOfTime.SECONDS
    VALID_UNITS = {
        UnitOfTime.MICROSECONDS,
        UnitOfTime.MILLISECONDS,
        UnitOfTime.SECONDS,
        UnitOfTime.MINUTES,
        UnitOfTime.HOURS,
        UnitOfTime.DAYS,
        UnitOfTime.WEEKS,
    }
    _UNIT_CONVERSION = {
        UnitOfTime.MICROSECONDS: 1000000,
        UnitOfTime.MILLISECONDS: 1000,
        UnitOfTime.SECONDS: 1,
        UnitOfTime.MINUTES: 1 / _MIN_TO_SEC,
        UnitOfTime.HOURS: 1 / _HRS_TO_SECS,
        UnitOfTime.DAYS: 1 / _DAYS_TO_SECS,
        UnitOfTime.WEEKS: 1 / (7 * _DAYS_TO_SECS),
    }


class ElectricCurrentConverter(BaseUnitConverter):
    """Utility to convert electric current values."""

    UNIT_CLASS = "electric_current"
    BASE_UNIT = UnitOfElectricCurrent.AMPERE
    VALID_UNITS = set(UnitOfElectricCurrent)
    _UNIT_CONVERSION = {
        UnitOfElectricCurrent.AMPERE: 1,
        UnitOfElectricCurrent.MILLIAMPERE: 1e3,
    }


class ElectricPotentialConverter(BaseUnitConverter):
    """Utility to convert electric potential values."""

    UNIT_CLASS = "voltage"
    BASE_UNIT = UnitOfElectricPotential.VOLT
    VALID_UNITS = set(UnitOfElectricPotential)
    _UNIT_CONVERSION = {
        UnitOfElectricPotential.VOLT: 1,
        UnitOfElectricPotential.MILLIVOLT: 1e3,
        UnitOfElectricPotential.MICROVOLT: 1e6,
        UnitOfElectricPotential.KILOVOLT: 1 / 1e3,
        UnitOfElectricPotential.MEGAVOLT: 1 / 1e6,
    }


class EnergyConverter(BaseUnitConverter):
    """Utility to convert energy values."""

    UNIT_CLASS = "energy"
    BASE_UNIT = UnitOfEnergy.KILO_WATT_HOUR
    VALID_UNITS = set(UnitOfEnergy)
    _UNIT_CONVERSION = {
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


class EnergyDistanceConverter(BaseUnitConverter):
    """Utility to convert vehicle energy consumption values."""

    UNIT_CLASS = "energy_distance"
    BASE_UNIT = UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM
    VALID_UNITS = set(UnitOfEnergyDistance)
    _UNIT_INVERSES = {
        UnitOfEnergyDistance.KM_PER_KILO_WATT_HOUR,
        UnitOfEnergyDistance.MILES_PER_KILO_WATT_HOUR,
    }
    _UNIT_CONVERSION = {
        UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM: 1,
        UnitOfEnergyDistance.WATT_HOUR_PER_KM: 10,
        UnitOfEnergyDistance.MILES_PER_KILO_WATT_HOUR: 100 * _KM_TO_M / _MILE_TO_M,
        UnitOfEnergyDistance.KM_PER_KILO_WATT_HOUR: 100,
    }


class InformationConverter(BaseUnitConverter):
    """Utility to convert information values."""

    UNIT_CLASS = "information"
    BASE_UNIT = UnitOfInformation.BITS
    VALID_UNITS = set(UnitOfInformation)
    _UNIT_CONVERSION = {
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


class MassConverter(BaseUnitConverter):
    """Utility to convert mass values."""

    UNIT_CLASS = "mass"
    BASE_UNIT = UnitOfMass.GRAMS
    VALID_UNITS = set(UnitOfMass)
    _UNIT_CONVERSION = {
        UnitOfMass.MICROGRAMS: 1 * 1000 * 1000,
        UnitOfMass.MILLIGRAMS: 1 * 1000,
        UnitOfMass.GRAMS: 1,
        UnitOfMass.KILOGRAMS: 1 / 1000,
        UnitOfMass.OUNCES: 1 / _OUNCE_TO_G,
        UnitOfMass.POUNDS: 1 / _POUND_TO_G,
        UnitOfMass.STONES: 1 / _STONE_TO_G,
    }


class MassVolumeConcentrationConverter(BaseUnitConverter):
    """Utility to convert mass volume concentration values."""

    UNIT_CLASS = "concentration"
    BASE_UNIT = UnitOfConcentration.GRAMS_PER_CUBIC_METER
    VALID_UNITS = {
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER,
        UnitOfConcentration.MILLIGRAMS_PER_CUBIC_METER,
        UnitOfConcentration.GRAMS_PER_CUBIC_METER,
    }
    _UNIT_CONVERSION = {
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER: 1_000_000.0,  # 1000 µg/m³ = 1 mg/m³
        UnitOfConcentration.MILLIGRAMS_PER_CUBIC_METER: 1000.0,  # 1000 mg/m³ = 1 g/m³
        UnitOfConcentration.GRAMS_PER_CUBIC_METER: 1,
    }


class NitrogenDioxideConcentrationConverter(BaseUnitConverter):
    """Convert nitrogen dioxide ratio to mass per volume."""

    UNIT_CLASS = "nitrogen_dioxide"
    BASE_UNIT = UnitOfConcentration.PARTS_PER_BILLION
    VALID_UNITS = {
        UnitOfConcentration.PARTS_PER_BILLION,
        UnitOfConcentration.PARTS_PER_MILLION,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER,
    }
    _UNIT_CONVERSION = {
        UnitOfConcentration.PARTS_PER_BILLION: 1,
        UnitOfConcentration.PARTS_PER_MILLION: 1e-3,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER: (
            _NITROGEN_DIOXIDE_MOLAR_MASS / _AMBIENT_IDEAL_GAS_MOLAR_VOLUME * 1e-3
        ),
    }


class NitrogenMonoxideConcentrationConverter(BaseUnitConverter):
    """Convert nitrogen monoxide ratio to mass per volume."""

    UNIT_CLASS = "nitrogen_monoxide"
    BASE_UNIT = UnitOfConcentration.PARTS_PER_BILLION
    VALID_UNITS = {
        UnitOfConcentration.PARTS_PER_BILLION,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER,
    }
    _UNIT_CONVERSION = {
        UnitOfConcentration.PARTS_PER_BILLION: 1,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER: (
            _NITROGEN_MONOXIDE_MOLAR_MASS / _AMBIENT_IDEAL_GAS_MOLAR_VOLUME * 1e-3
        ),
    }


class OzoneConcentrationConverter(BaseUnitConverter):
    """Convert ozone ratio to mass per volume."""

    UNIT_CLASS = "ozone"
    BASE_UNIT = UnitOfConcentration.PARTS_PER_BILLION
    VALID_UNITS = {
        UnitOfConcentration.PARTS_PER_BILLION,
        UnitOfConcentration.PARTS_PER_MILLION,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER,
    }
    _UNIT_CONVERSION = {
        UnitOfConcentration.PARTS_PER_BILLION: 1,
        UnitOfConcentration.PARTS_PER_MILLION: 1e-3,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER: (
            _OZONE_MOLAR_MASS / _AMBIENT_IDEAL_GAS_MOLAR_VOLUME * 1e-3
        ),
    }


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    UNIT_CLASS = "power"
    BASE_UNIT = UnitOfPower.WATT
    VALID_UNITS = set(UnitOfPower)
    _UNIT_CONVERSION = {
        UnitOfPower.MILLIWATT: 1 * 1000,
        UnitOfPower.WATT: 1,
        UnitOfPower.KILO_WATT: 1 / 1000,
        UnitOfPower.MEGA_WATT: 1 / 1e6,
        UnitOfPower.GIGA_WATT: 1 / 1e9,
        UnitOfPower.TERA_WATT: 1 / 1e12,
        UnitOfPower.BTU_PER_HOUR: 1 / 0.29307107,
    }


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    UNIT_CLASS = "pressure"
    BASE_UNIT = UnitOfPressure.PA
    VALID_UNITS = set(UnitOfPressure)
    _UNIT_CONVERSION = {
        UnitOfPressure.MILLIPASCAL: 1 * 1000,
        UnitOfPressure.PA: 1,
        UnitOfPressure.HPA: 1 / 100,
        UnitOfPressure.KPA: 1 / 1000,
        UnitOfPressure.BAR: 1 / 100000,
        UnitOfPressure.CBAR: 1 / 1000,
        UnitOfPressure.MBAR: 1 / 100,
        UnitOfPressure.INHG: 1
        / (_IN_TO_M * 1000 * _STANDARD_GRAVITY * _MERCURY_DENSITY),
        UnitOfPressure.INH2O: 1 / _INH2O_TO_PA,
        UnitOfPressure.PSI: 1 / 6894.757,
        UnitOfPressure.MMHG: 1
        / (_MM_TO_M * 1000 * _STANDARD_GRAVITY * _MERCURY_DENSITY),
    }


class ReactiveEnergyConverter(BaseUnitConverter):
    """Utility to convert reactive energy values."""

    UNIT_CLASS = "reactive_energy"
    BASE_UNIT = UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR
    VALID_UNITS = set(UnitOfReactiveEnergy)
    _UNIT_CONVERSION = {
        UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR: 1,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR: 1 / 1e3,
    }


class ReactivePowerConverter(BaseUnitConverter):
    """Utility to convert reactive power values."""

    UNIT_CLASS = "reactive_power"
    BASE_UNIT = UnitOfReactivePower.VOLT_AMPERE_REACTIVE
    VALID_UNITS = set(UnitOfReactivePower)
    _UNIT_CONVERSION = {
        UnitOfReactivePower.MILLIVOLT_AMPERE_REACTIVE: 1 * 1000,
        UnitOfReactivePower.VOLT_AMPERE_REACTIVE: 1,
        UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE: 1 / 1000,
    }


class SpeedConverter(BaseUnitConverter):
    """Utility to convert speed values."""

    UNIT_CLASS = "speed"
    BASE_UNIT = UnitOfSpeed.METERS_PER_SECOND
    VALID_UNITS = {
        UnitOfVolumetricFlux.INCHES_PER_DAY,
        UnitOfVolumetricFlux.INCHES_PER_HOUR,
        UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        UnitOfSpeed.INCHES_PER_SECOND,
        UnitOfSpeed.FEET_PER_SECOND,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        UnitOfSpeed.KNOTS,
        UnitOfSpeed.METERS_PER_MINUTE,
        UnitOfSpeed.METERS_PER_SECOND,
        UnitOfSpeed.MILES_PER_HOUR,
        UnitOfSpeed.MILLIMETERS_PER_SECOND,
        UnitOfSpeed.BEAUFORT,
    }
    _UNIT_CONVERSION = {
        UnitOfVolumetricFlux.INCHES_PER_DAY: _DAYS_TO_SECS / _IN_TO_M,
        UnitOfVolumetricFlux.INCHES_PER_HOUR: _HRS_TO_SECS / _IN_TO_M,
        UnitOfVolumetricFlux.MILLIMETERS_PER_DAY: _DAYS_TO_SECS / _MM_TO_M,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR: _HRS_TO_SECS / _MM_TO_M,
        UnitOfSpeed.FEET_PER_SECOND: 1 / _FOOT_TO_M,
        UnitOfSpeed.INCHES_PER_SECOND: 1 / _IN_TO_M,
        UnitOfSpeed.KILOMETERS_PER_HOUR: _HRS_TO_SECS / _KM_TO_M,
        UnitOfSpeed.KNOTS: _HRS_TO_SECS / _NAUTICAL_MILE_TO_M,
        UnitOfSpeed.METERS_PER_MINUTE: _MIN_TO_SEC,
        UnitOfSpeed.METERS_PER_SECOND: 1,
        UnitOfSpeed.MILLIMETERS_PER_SECOND: 1 / _MM_TO_M,
        UnitOfSpeed.MILES_PER_HOUR: _HRS_TO_SECS / _MILE_TO_M,
        UnitOfSpeed.BEAUFORT: [
            (UnitConvertOpType.SCALE, 1 / 0.836),
            (UnitConvertOpType.POWER, 2 / 3),
            (UnitConvertOpType.ROUND, 0),
        ],
    }


class SulphurDioxideConcentrationConverter(BaseUnitConverter):
    """Convert sulphur dioxide ratio to mass per volume."""

    UNIT_CLASS = "sulphur_dioxide"
    BASE_UNIT = UnitOfConcentration.PARTS_PER_BILLION
    VALID_UNITS = {
        UnitOfConcentration.PARTS_PER_BILLION,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER,
    }
    _UNIT_CONVERSION = {
        UnitOfConcentration.PARTS_PER_BILLION: 1,
        UnitOfConcentration.MICROGRAMS_PER_CUBIC_METER: (
            _SULPHUR_DIOXIDE_MOLAR_MASS / _AMBIENT_IDEAL_GAS_MOLAR_VOLUME * 1e-3
        ),
    }


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    UNIT_CLASS = "temperature"
    BASE_UNIT = UnitOfTemperature.CELSIUS
    VALID_UNITS = set(UnitOfTemperature)
    _UNIT_CONVERSION = {
        UnitOfTemperature.CELSIUS: 1.0,
        UnitOfTemperature.FAHRENHEIT: [
            (UnitConvertOpType.SCALE, 1.8),
            (UnitConvertOpType.OFFSET, 32.0),
        ],
        UnitOfTemperature.KELVIN: [
            (UnitConvertOpType.OFFSET, 273.15),
        ],
    }

    @classmethod
    @deprecated_function(
        "TemperatureDeltaConverter.convert", breaks_in_ha_version="2026.12.0"
    )
    def convert_interval(cls, interval: float, from_unit: str, to_unit: str) -> float:
        """Convert a temperature interval from one unit to another.

        eg. a 10°C interval (10°C to 20°C) will return a 18°F (50°F to 68°F) interval

        For converting a temperature value, please use `convert` as this method
        skips floor adjustment.
        """
        # Perform conversion using TemperatureDeltaConverter.
        return TemperatureDeltaConverter.converter_factory(from_unit, to_unit)(interval)


class TemperatureDeltaConverter(BaseUnitConverter):
    """Utility to convert temperature intervals.

    eg. a 10°C interval (10°C to 20°C) will return a 18°F (50°F to 68°F) interval
    """

    UNIT_CLASS = "temperature_delta"
    BASE_UNIT = UnitOfTemperature.CELSIUS
    VALID_UNITS = set(UnitOfTemperature)
    _UNIT_CONVERSION = {
        UnitOfTemperature.CELSIUS: 1.0,
        UnitOfTemperature.FAHRENHEIT: 1.8,
        UnitOfTemperature.KELVIN: 1.0,
    }


class UnitlessRatioConverter(BaseUnitConverter):
    """Utility to convert unitless ratios."""

    UNIT_CLASS = "unitless"
    BASE_UNIT = None
    VALID_UNITS = {
        None,
        UnitOfConcentration.PARTS_PER_BILLION,
        UnitOfConcentration.PARTS_PER_MILLION,
        PERCENTAGE,
    }
    _UNIT_CONVERSION = {
        None: 1,
        UnitOfConcentration.PARTS_PER_BILLION: 1000000000,
        UnitOfConcentration.PARTS_PER_MILLION: 1000000,
        PERCENTAGE: 100,
    }


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    UNIT_CLASS = "volume"
    BASE_UNIT = UnitOfVolume.CUBIC_METERS
    VALID_UNITS = set(UnitOfVolume)
    _UNIT_CONVERSION = {
        UnitOfVolume.LITERS: 1 / _L_TO_CUBIC_METER,
        UnitOfVolume.MILLILITERS: 1 / _ML_TO_CUBIC_METER,
        UnitOfVolume.GALLONS: 1 / _GALLON_TO_CUBIC_METER,
        UnitOfVolume.FLUID_OUNCES: 1 / _FLUID_OUNCE_TO_CUBIC_METER,
        UnitOfVolume.CUBIC_METERS: 1,
        UnitOfVolume.CUBIC_FEET: 1 / _CUBIC_FOOT_TO_CUBIC_METER,
        UnitOfVolume.CENTUM_CUBIC_FEET: 1 / (100 * _CUBIC_FOOT_TO_CUBIC_METER),
        UnitOfVolume.MILLE_CUBIC_FEET: 1 / (1000 * _CUBIC_FOOT_TO_CUBIC_METER),
    }


class VolumeFlowRateConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    UNIT_CLASS = "volume_flow_rate"
    BASE_UNIT = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    VALID_UNITS = set(UnitOfVolumeFlowRate)
    _UNIT_CONVERSION = {
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR: 1,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_MINUTE: 1 / _HRS_TO_MINUTES,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_SECOND: 1 / _HRS_TO_SECS,
        UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE: 1
        / (_HRS_TO_MINUTES * _CUBIC_FOOT_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.LITERS_PER_HOUR: 1 / _L_TO_CUBIC_METER,
        UnitOfVolumeFlowRate.LITERS_PER_MINUTE: 1
        / (_HRS_TO_MINUTES * _L_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.LITERS_PER_SECOND: 1 / (_HRS_TO_SECS * _L_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.GALLONS_PER_HOUR: 1 / _GALLON_TO_CUBIC_METER,
        UnitOfVolumeFlowRate.GALLONS_PER_MINUTE: 1
        / (_HRS_TO_MINUTES * _GALLON_TO_CUBIC_METER),
        UnitOfVolumeFlowRate.GALLONS_PER_DAY: _DAYS_TO_HRS / _GALLON_TO_CUBIC_METER,
        UnitOfVolumeFlowRate.MILLILITERS_PER_SECOND: 1
        / (_HRS_TO_SECS * _ML_TO_CUBIC_METER),
    }
