"""Unit system helper class and methods."""
from __future__ import annotations

from numbers import Number
from typing import TYPE_CHECKING, Final

import voluptuous as vol

from homeassistant.const import (
    ACCUMULATED_PRECIPITATION,
    LENGTH,
    MASS,
    PRESSURE,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    WIND_SPEED,
    UnitOfLength,
    UnitOfMass,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumetricFlux,
)

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

MASS_UNITS: set[str] = {
    UnitOfMass.POUNDS,
    UnitOfMass.OUNCES,
    UnitOfMass.KILOGRAMS,
    UnitOfMass.GRAMS,
}

PRESSURE_UNITS = PressureConverter.VALID_UNITS

VOLUME_UNITS = VolumeConverter.VALID_UNITS

WIND_SPEED_UNITS = SpeedConverter.VALID_UNITS

TEMPERATURE_UNITS: set[str] = {UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS}


def _is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == LENGTH:
        return unit in LENGTH_UNITS
    if unit_type == ACCUMULATED_PRECIPITATION:
        return unit in LENGTH_UNITS
    if unit_type == WIND_SPEED:
        return unit in WIND_SPEED_UNITS
    if unit_type == TEMPERATURE:
        return unit in TEMPERATURE_UNITS
    if unit_type == MASS:
        return unit in MASS_UNITS
    if unit_type == VOLUME:
        return unit in VOLUME_UNITS
    if unit_type == PRESSURE:
        return unit in PRESSURE_UNITS
    return False


class UnitSystem:
    """A container for units of measure."""

    def __init__(
        self,
        name: str,
        *,
        accumulated_precipitation: UnitOfPrecipitationDepth,
        conversions: dict[tuple[SensorDeviceClass | str | None, str | None], str],
        length: UnitOfLength,
        mass: UnitOfMass,
        pressure: UnitOfPressure,
        temperature: UnitOfTemperature,
        volume: UnitOfVolume,
        wind_speed: UnitOfSpeed,
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
        return SpeedConverter.convert(  # type: ignore[unreachable]
            wind_speed, from_unit, self.wind_speed_unit
        )

    def volume(self, volume: float | None, from_unit: str) -> float:
        """Convert the given volume to this unit system."""
        if not isinstance(volume, Number):
            raise TypeError(f"{volume!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return VolumeConverter.convert(  # type: ignore[unreachable]
            volume, from_unit, self.volume_unit
        )

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
    accumulated_precipitation=UnitOfPrecipitationDepth.MILLIMETERS,
    conversions={
        # Force atmospheric pressures to hPa
        **{
            ("atmospheric_pressure", unit): UnitOfPressure.HPA
            for unit in UnitOfPressure
            if unit != UnitOfPressure.HPA
        },
        # Convert non-metric distances
        ("distance", UnitOfLength.FEET): UnitOfLength.METERS,
        ("distance", UnitOfLength.INCHES): UnitOfLength.MILLIMETERS,
        ("distance", UnitOfLength.MILES): UnitOfLength.KILOMETERS,
        ("distance", UnitOfLength.YARDS): UnitOfLength.METERS,
        # Convert non-metric volumes of gas meters
        ("gas", UnitOfVolume.CENTUM_CUBIC_FEET): UnitOfVolume.CUBIC_METERS,
        ("gas", UnitOfVolume.CUBIC_FEET): UnitOfVolume.CUBIC_METERS,
        # Convert non-metric precipitation
        ("precipitation", UnitOfLength.INCHES): UnitOfLength.MILLIMETERS,
        # Convert non-metric precipitation intensity
        (
            "precipitation_intensity",
            UnitOfVolumetricFlux.INCHES_PER_DAY,
        ): UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        (
            "precipitation_intensity",
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ): UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        # Convert non-metric pressure
        ("pressure", UnitOfPressure.PSI): UnitOfPressure.KPA,
        ("pressure", UnitOfPressure.INHG): UnitOfPressure.HPA,
        # Convert non-metric speeds except knots to km/h
        ("speed", UnitOfSpeed.FEET_PER_SECOND): UnitOfSpeed.KILOMETERS_PER_HOUR,
        ("speed", UnitOfSpeed.MILES_PER_HOUR): UnitOfSpeed.KILOMETERS_PER_HOUR,
        (
            "speed",
            UnitOfVolumetricFlux.INCHES_PER_DAY,
        ): UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        (
            "speed",
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ): UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        # Convert non-metric volumes
        ("volume", UnitOfVolume.CENTUM_CUBIC_FEET): UnitOfVolume.CUBIC_METERS,
        ("volume", UnitOfVolume.CUBIC_FEET): UnitOfVolume.CUBIC_METERS,
        ("volume", UnitOfVolume.FLUID_OUNCES): UnitOfVolume.MILLILITERS,
        ("volume", UnitOfVolume.GALLONS): UnitOfVolume.LITERS,
        # Convert non-metric volumes of water meters
        ("water", UnitOfVolume.CENTUM_CUBIC_FEET): UnitOfVolume.CUBIC_METERS,
        ("water", UnitOfVolume.CUBIC_FEET): UnitOfVolume.CUBIC_METERS,
        ("water", UnitOfVolume.GALLONS): UnitOfVolume.LITERS,
        # Convert wind speeds except knots to km/h
        **{
            ("wind_speed", unit): UnitOfSpeed.KILOMETERS_PER_HOUR
            for unit in UnitOfSpeed
            if unit not in (UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.KNOTS)
        },
    },
    length=UnitOfLength.KILOMETERS,
    mass=UnitOfMass.GRAMS,
    pressure=UnitOfPressure.PA,
    temperature=UnitOfTemperature.CELSIUS,
    volume=UnitOfVolume.LITERS,
    wind_speed=UnitOfSpeed.METERS_PER_SECOND,
)

US_CUSTOMARY_SYSTEM = UnitSystem(
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
    accumulated_precipitation=UnitOfPrecipitationDepth.INCHES,
    conversions={
        # Force atmospheric pressures to inHg
        **{
            ("atmospheric_pressure", unit): UnitOfPressure.INHG
            for unit in UnitOfPressure
            if unit != UnitOfPressure.INHG
        },
        # Convert non-USCS distances
        ("distance", UnitOfLength.CENTIMETERS): UnitOfLength.INCHES,
        ("distance", UnitOfLength.KILOMETERS): UnitOfLength.MILES,
        ("distance", UnitOfLength.METERS): UnitOfLength.FEET,
        ("distance", UnitOfLength.MILLIMETERS): UnitOfLength.INCHES,
        # Convert non-USCS volumes of gas meters
        ("gas", UnitOfVolume.CUBIC_METERS): UnitOfVolume.CUBIC_FEET,
        # Convert non-USCS precipitation
        ("precipitation", UnitOfLength.CENTIMETERS): UnitOfLength.INCHES,
        ("precipitation", UnitOfLength.MILLIMETERS): UnitOfLength.INCHES,
        # Convert non-USCS precipitation intensity
        (
            "precipitation_intensity",
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        ): UnitOfVolumetricFlux.INCHES_PER_DAY,
        (
            "precipitation_intensity",
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        ): UnitOfVolumetricFlux.INCHES_PER_HOUR,
        # Convert non-USCS pressure
        ("pressure", UnitOfPressure.MBAR): UnitOfPressure.PSI,
        ("pressure", UnitOfPressure.CBAR): UnitOfPressure.PSI,
        ("pressure", UnitOfPressure.BAR): UnitOfPressure.PSI,
        ("pressure", UnitOfPressure.PA): UnitOfPressure.PSI,
        ("pressure", UnitOfPressure.HPA): UnitOfPressure.PSI,
        ("pressure", UnitOfPressure.KPA): UnitOfPressure.PSI,
        ("pressure", UnitOfPressure.MMHG): UnitOfPressure.INHG,
        # Convert non-USCS speeds, except knots, to mph
        ("speed", UnitOfSpeed.METERS_PER_SECOND): UnitOfSpeed.MILES_PER_HOUR,
        ("speed", UnitOfSpeed.KILOMETERS_PER_HOUR): UnitOfSpeed.MILES_PER_HOUR,
        (
            "speed",
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        ): UnitOfVolumetricFlux.INCHES_PER_DAY,
        (
            "speed",
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        ): UnitOfVolumetricFlux.INCHES_PER_HOUR,
        # Convert non-USCS volumes
        ("volume", UnitOfVolume.CUBIC_METERS): UnitOfVolume.CUBIC_FEET,
        ("volume", UnitOfVolume.LITERS): UnitOfVolume.GALLONS,
        ("volume", UnitOfVolume.MILLILITERS): UnitOfVolume.FLUID_OUNCES,
        # Convert non-USCS volumes of water meters
        ("water", UnitOfVolume.CUBIC_METERS): UnitOfVolume.CUBIC_FEET,
        ("water", UnitOfVolume.LITERS): UnitOfVolume.GALLONS,
        # Convert wind speeds except knots to mph
        **{
            ("wind_speed", unit): UnitOfSpeed.MILES_PER_HOUR
            for unit in UnitOfSpeed
            if unit not in (UnitOfSpeed.KNOTS, UnitOfSpeed.MILES_PER_HOUR)
        },
    },
    length=UnitOfLength.MILES,
    mass=UnitOfMass.POUNDS,
    pressure=UnitOfPressure.PSI,
    temperature=UnitOfTemperature.FAHRENHEIT,
    volume=UnitOfVolume.GALLONS,
    wind_speed=UnitOfSpeed.MILES_PER_HOUR,
)

IMPERIAL_SYSTEM = US_CUSTOMARY_SYSTEM
"""IMPERIAL_SYSTEM is deprecated. Please use US_CUSTOMARY_SYSTEM instead."""
