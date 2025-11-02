"""Temperature helpers for Home Assistant."""

from numbers import Number

from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import (
    TemperatureConverter,
    TemperatureDeltaConverter,
)


def display_temp(
    hass: HomeAssistant, temperature: float | None, unit: str, precision: float
) -> float | None:
    """Convert temperature into preferred units/precision for display."""

    if temperature is None:
        return temperature

    # If the temperature is not a number this can cause issues
    # with Polymer components, so bail early there.
    if not isinstance(temperature, Number):
        raise TypeError(f"Temperature is not a number: {temperature}")

    ha_unit = hass.config.units.temperature_unit

    if unit != ha_unit:
        temperature = TemperatureConverter.converter_factory(unit, ha_unit)(temperature)

    # Round in the units appropriate
    if precision == PRECISION_HALVES:
        return round(temperature * 2) / 2.0
    if precision == PRECISION_TENTHS:
        return round(temperature, 1)
    # Integer as a fall back (PRECISION_WHOLE)
    return round(temperature)


def display_temp_interval(
    hass: HomeAssistant, interval: float, unit: str, precision: float
) -> float:
    """Convert temperature interval into preferred units/precision for display."""

    if not isinstance(interval, Number):
        raise TypeError(f"Temperature interval is not a number: {interval}")

    ha_unit = hass.config.units.temperature_unit

    if unit != ha_unit:
        interval = TemperatureDeltaConverter.convert(interval, unit, ha_unit)

    # IEEE rounding would produce round(0.5) == 0 that seems unnatural.
    # Ensure 0.5 -> 1 while rounding to int
    if precision == PRECISION_HALVES:
        return (round(interval * 2 + 1) - 1) / 2.0
    if precision == PRECISION_TENTHS:
        return round(interval, 1)
    return round(interval + 1) - 1
