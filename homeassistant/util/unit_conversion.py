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

    DEVICE_CLASS: str
    NORMALIZED_UNIT: str
    VALID_UNITS: tuple[str, ...]
    convert: Callable[[float, str, str], float]


class EnergyConverter(BaseUnitConverter):
    """Utility to convert energy values."""

    DEVICE_CLASS = "energy"
    NORMALIZED_UNIT = energy_util.NORMALIZED_UNIT
    VALID_UNITS = energy_util.VALID_UNITS
    convert = energy_util.convert


class PowerConverter(BaseUnitConverter):
    """Utility to convert power values."""

    DEVICE_CLASS = "power"
    NORMALIZED_UNIT = power_util.NORMALIZED_UNIT
    VALID_UNITS = power_util.VALID_UNITS
    convert = power_util.convert


class PressureConverter(BaseUnitConverter):
    """Utility to convert pressure values."""

    DEVICE_CLASS = "pressure"
    NORMALIZED_UNIT = pressure_util.NORMALIZED_UNIT
    VALID_UNITS = pressure_util.VALID_UNITS
    convert = pressure_util.convert


class TemperatureConverter(BaseUnitConverter):
    """Utility to convert temperature values."""

    DEVICE_CLASS = "temperature"
    NORMALIZED_UNIT = temperature_util.NORMALIZED_UNIT
    VALID_UNITS = temperature_util.VALID_UNITS
    convert = temperature_util.convert


class VolumeConverter(BaseUnitConverter):
    """Utility to convert volume values."""

    DEVICE_CLASS = "volume"
    NORMALIZED_UNIT = volume_util.NORMALIZED_UNIT
    VALID_UNITS = volume_util.VALID_UNITS
    convert = volume_util.convert
