"""Unit system helper class and methods."""
from __future__ import annotations

from numbers import Number
from typing import TYPE_CHECKING, Final

import voluptuous as vol

from homeassistant.const import (
    ACCUMULATED_PRECIPITATION,
    LENGTH,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
    MASS,
    MASS_GRAMS,
    MASS_KILOGRAMS,
    MASS_OUNCES,
    MASS_POUNDS,
    PRECIPITATION_INCHES,
    PRECIPITATION_MILLIMETERS,
    PRESSURE,
    PRESSURE_PA,
    PRESSURE_PSI,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    WIND_SPEED,
)
from homeassistant.helpers.frame import report

from .unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    VolumeConverter,
)

if TYPE_CHECKING:
    from homeassistant.components.sensor import SensorDeviceClass

_CONF_UNIT_SYSTEM_IMPERIAL: Final = "imperial"
_CONF_UNIT_SYSTEM_METRIC: Final = "metric"
_CONF_UNIT_SYSTEM_US_CUSTOMARY: Final = "us_customary"

LENGTH_UNITS = DistanceConverter.VALID_UNITS

MASS_UNITS: set[str] = {MASS_POUNDS, MASS_OUNCES, MASS_KILOGRAMS, MASS_GRAMS}

PRESSURE_UNITS = PressureConverter.VALID_UNITS

VOLUME_UNITS = VolumeConverter.VALID_UNITS

WIND_SPEED_UNITS = SpeedConverter.VALID_UNITS

TEMPERATURE_UNITS: set[str] = {TEMP_FAHRENHEIT, TEMP_CELSIUS}


def _is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == LENGTH:
        units = LENGTH_UNITS
    elif unit_type == ACCUMULATED_PRECIPITATION:
        units = LENGTH_UNITS
    elif unit_type == WIND_SPEED:
        units = WIND_SPEED_UNITS
    elif unit_type == TEMPERATURE:
        units = TEMPERATURE_UNITS
    elif unit_type == MASS:
        units = MASS_UNITS
    elif unit_type == VOLUME:
        units = VOLUME_UNITS
    elif unit_type == PRESSURE:
        units = PRESSURE_UNITS
    else:
        return False

    return unit in units


class UnitSystem:
    """A container for units of measure."""

    def __init__(
        self,
        name: str,
        *,
        accumulated_precipitation: str,
        conversions: dict[tuple[str | None, str | None], str],
        length: str,
        mass: str,
        pressure: str,
        temperature: str,
        volume: str,
        wind_speed: str,
    ) -> None:
        """Initialize the unit system object."""
        errors: str = ", ".join(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type)
            for unit, unit_type in (
                (accumulated_precipitation, ACCUMULATED_PRECIPITATION),
                (temperature, TEMPERATURE),
                (length, LENGTH),
                (wind_speed, WIND_SPEED),
                (volume, VOLUME),
                (mass, MASS),
                (pressure, PRESSURE),
            )
            if not _is_valid_unit(unit, unit_type)
        )

        if errors:
            raise ValueError(errors)

        self._name = name
        self.accumulated_precipitation_unit = accumulated_precipitation
        self.temperature_unit = temperature
        self.length_unit = length
        self.mass_unit = mass
        self.pressure_unit = pressure
        self.volume_unit = volume
        self.wind_speed_unit = wind_speed
        self._conversions = conversions

    @property
    def name(self) -> str:
        """Return the name of the unit system."""
        report(
            "accesses the `name` property of the unit system. "
            "This is deprecated and will stop working in Home Assistant 2023.1. "
            "Please adjust to use instance check instead.",
            error_if_core=False,
        )
        if self is IMPERIAL_SYSTEM:
            # kept for compatibility reasons, with associated warning above
            return _CONF_UNIT_SYSTEM_IMPERIAL
        return self._name

    @property
    def is_metric(self) -> bool:
        """Determine if this is the metric unit system."""
        report(
            "accesses the `is_metric` property of the unit system. "
            "This is deprecated and will stop working in Home Assistant 2023.1. "
            "Please adjust to use instance check instead.",
            error_if_core=False,
        )
        return self is METRIC_SYSTEM

    def temperature(self, temperature: float, from_unit: str) -> float:
        """Convert the given temperature to this unit system."""
        if not isinstance(temperature, Number):
            raise TypeError(f"{temperature!s} is not a numeric value.")

        return TemperatureConverter.convert(
            temperature, from_unit, self.temperature_unit
        )

    def length(self, length: float | None, from_unit: str) -> float:
        """Convert the given length to this unit system."""
        if not isinstance(length, Number):
            raise TypeError(f"{length!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return DistanceConverter.convert(  # type: ignore[unreachable]
            length, from_unit, self.length_unit
        )

    def accumulated_precipitation(self, precip: float | None, from_unit: str) -> float:
        """Convert the given length to this unit system."""
        if not isinstance(precip, Number):
            raise TypeError(f"{precip!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return DistanceConverter.convert(  # type: ignore[unreachable]
            precip, from_unit, self.accumulated_precipitation_unit
        )

    def pressure(self, pressure: float | None, from_unit: str) -> float:
        """Convert the given pressure to this unit system."""
        if not isinstance(pressure, Number):
            raise TypeError(f"{pressure!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return PressureConverter.convert(  # type: ignore[unreachable]
            pressure, from_unit, self.pressure_unit
        )

    def wind_speed(self, wind_speed: float | None, from_unit: str) -> float:
        """Convert the given wind_speed to this unit system."""
        if not isinstance(wind_speed, Number):
            raise TypeError(f"{wind_speed!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return SpeedConverter.convert(wind_speed, from_unit, self.wind_speed_unit)  # type: ignore[unreachable]

    def volume(self, volume: float | None, from_unit: str) -> float:
        """Convert the given volume to this unit system."""
        if not isinstance(volume, Number):
            raise TypeError(f"{volume!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return VolumeConverter.convert(volume, from_unit, self.volume_unit)  # type: ignore[unreachable]

    def as_dict(self) -> dict[str, str]:
        """Convert the unit system to a dictionary."""
        return {
            LENGTH: self.length_unit,
            ACCUMULATED_PRECIPITATION: self.accumulated_precipitation_unit,
            MASS: self.mass_unit,
            PRESSURE: self.pressure_unit,
            TEMPERATURE: self.temperature_unit,
            VOLUME: self.volume_unit,
            WIND_SPEED: self.wind_speed_unit,
        }

    def get_converted_unit(
        self,
        device_class: SensorDeviceClass | str | None,
        original_unit: str | None,
    ) -> str | None:
        """Return converted unit given a device class or an original unit."""
        return self._conversions.get((device_class, original_unit))


def get_unit_system(key: str) -> UnitSystem:
    """Get unit system based on key."""
    if key == _CONF_UNIT_SYSTEM_US_CUSTOMARY:
        return US_CUSTOMARY_SYSTEM
    if key == _CONF_UNIT_SYSTEM_METRIC:
        return METRIC_SYSTEM
    raise ValueError(f"`{key}` is not a valid unit system key")


def _deprecated_unit_system(value: str) -> str:
    """Convert deprecated unit system."""

    if value == _CONF_UNIT_SYSTEM_IMPERIAL:
        # need to add warning in 2023.1
        return _CONF_UNIT_SYSTEM_US_CUSTOMARY
    return value


validate_unit_system = vol.All(
    vol.Lower,
    _deprecated_unit_system,
    vol.Any(_CONF_UNIT_SYSTEM_METRIC, _CONF_UNIT_SYSTEM_US_CUSTOMARY),
)

METRIC_SYSTEM = UnitSystem(
    _CONF_UNIT_SYSTEM_METRIC,
    accumulated_precipitation=PRECIPITATION_MILLIMETERS,
    conversions={
        ("distance", LENGTH_FEET): LENGTH_METERS,
        ("distance", LENGTH_INCHES): LENGTH_CENTIMETERS,
        ("distance", LENGTH_MILES): LENGTH_KILOMETERS,
        ("distance", LENGTH_YARD): LENGTH_METERS,
    },
    length=LENGTH_KILOMETERS,
    mass=MASS_GRAMS,
    pressure=PRESSURE_PA,
    temperature=TEMP_CELSIUS,
    volume=VOLUME_LITERS,
    wind_speed=SPEED_METERS_PER_SECOND,
)

US_CUSTOMARY_SYSTEM = UnitSystem(
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
    accumulated_precipitation=PRECIPITATION_INCHES,
    conversions={
        ("distance", LENGTH_CENTIMETERS): LENGTH_INCHES,
        ("distance", LENGTH_KILOMETERS): LENGTH_MILES,
        ("distance", LENGTH_METERS): LENGTH_FEET,
        ("distance", LENGTH_MILLIMETERS): LENGTH_INCHES,
    },
    length=LENGTH_MILES,
    mass=MASS_POUNDS,
    pressure=PRESSURE_PSI,
    temperature=TEMP_FAHRENHEIT,
    volume=VOLUME_GALLONS,
    wind_speed=SPEED_MILES_PER_HOUR,
)

IMPERIAL_SYSTEM = US_CUSTOMARY_SYSTEM
"""IMPERIAL_SYSTEM is deprecated. Please use US_CUSTOMARY_SYSTEM instead."""
