"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable

from . import (
    energy as energy_util,
    power as power_util,
    pressure as pressure_util,
    temperature as temperature_util,
    volume as volume_util,
)


class BaseUnitConverter:
    """Define the format of a conversion utility."""

    NORMALIZED_UNIT: str
    VALID_UNITS: tuple[str, ...]
    convert: Callable[[float, str, str], float]


class EnergyConverter(BaseUnitConverter):
    """Utility to convert energy values."""

    NORMALIZED_UNIT = energy_util.NORMALIZED_UNIT
    VALID_UNITS = energy_util.VALID_UNITS
    convert = energy_util.convert


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    NORMALIZED_UNIT = power_util.NORMALIZED_UNIT
    VALID_UNITS = power_util.VALID_UNITS
    convert = power_util.convert


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    NORMALIZED_UNIT = pressure_util.NORMALIZED_UNIT
    VALID_UNITS = pressure_util.VALID_UNITS
    convert = pressure_util.convert


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    NORMALIZED_UNIT = temperature_util.NORMALIZED_UNIT
    VALID_UNITS = temperature_util.VALID_UNITS
    convert = temperature_util.convert


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    NORMALIZED_UNIT = volume_util.NORMALIZED_UNIT
    VALID_UNITS = volume_util.VALID_UNITS
    convert = volume_util.convert
