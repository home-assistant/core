"""Unit system helper class and methods."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    LENGTH,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    MASS,
    MASS_GRAMS,
    MASS_KILOGRAMS,
    MASS_OUNCES,
    MASS_POUNDS,
    PRESSURE,
    PRESSURE_PA,
    PRESSURE_PSI,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.util import (
    distance as distance_util,
    pressure as pressure_util,
    temperature as temperature_util,
    volume as volume_util,
)

# mypy: disallow-any-generics

LENGTH_UNITS = distance_util.VALID_UNITS

MASS_UNITS: tuple[str, ...] = (MASS_POUNDS, MASS_OUNCES, MASS_KILOGRAMS, MASS_GRAMS)

PRESSURE_UNITS = pressure_util.VALID_UNITS

VOLUME_UNITS = volume_util.VALID_UNITS

TEMPERATURE_UNITS: tuple[str, ...] = (TEMP_FAHRENHEIT, TEMP_CELSIUS)


def is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == LENGTH:
        units = LENGTH_UNITS
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
        temperature: str,
        length: str,
        volume: str,
        mass: str,
        pressure: str,
    ) -> None:
        """Initialize the unit system object."""
        errors: str = ", ".join(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type)
            for unit, unit_type in (
                (temperature, TEMPERATURE),
                (length, LENGTH),
                (volume, VOLUME),
                (mass, MASS),
                (pressure, PRESSURE),
            )
            if not is_valid_unit(unit, unit_type)
        )

        if errors:
            raise ValueError(errors)

        self.name = name
        self.temperature_unit = temperature
        self.length_unit = length
        self.mass_unit = mass
        self.pressure_unit = pressure
        self.volume_unit = volume

    @property
    def is_metric(self) -> bool:
        """Determine if this is the metric unit system."""
        return self.name == CONF_UNIT_SYSTEM_METRIC

    def temperature(self, temperature: float, from_unit: str) -> float:
        """Convert the given temperature to this unit system."""
        if not isinstance(temperature, Number):
            raise TypeError(f"{temperature!s} is not a numeric value.")

        return temperature_util.convert(temperature, from_unit, self.temperature_unit)

    def length(self, length: float | None, from_unit: str) -> float:
        """Convert the given length to this unit system."""
        if not isinstance(length, Number):
            raise TypeError(f"{length!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return distance_util.convert(  # type: ignore
            length, from_unit, self.length_unit
        )

    def pressure(self, pressure: float | None, from_unit: str) -> float:
        """Convert the given pressure to this unit system."""
        if not isinstance(pressure, Number):
            raise TypeError(f"{pressure!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return pressure_util.convert(  # type: ignore
            pressure, from_unit, self.pressure_unit
        )

    def volume(self, volume: float | None, from_unit: str) -> float:
        """Convert the given volume to this unit system."""
        if not isinstance(volume, Number):
            raise TypeError(f"{volume!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return volume_util.convert(volume, from_unit, self.volume_unit)  # type: ignore

    def as_dict(self) -> dict[str, str]:
        """Convert the unit system to a dictionary."""
        return {
            LENGTH: self.length_unit,
            MASS: self.mass_unit,
            PRESSURE: self.pressure_unit,
            TEMPERATURE: self.temperature_unit,
            VOLUME: self.volume_unit,
        }


METRIC_SYSTEM = UnitSystem(
    CONF_UNIT_SYSTEM_METRIC,
    TEMP_CELSIUS,
    LENGTH_KILOMETERS,
    VOLUME_LITERS,
    MASS_GRAMS,
    PRESSURE_PA,
)

IMPERIAL_SYSTEM = UnitSystem(
    CONF_UNIT_SYSTEM_IMPERIAL,
    TEMP_FAHRENHEIT,
    LENGTH_MILES,
    VOLUME_GALLONS,
    MASS_POUNDS,
    PRESSURE_PSI,
)
