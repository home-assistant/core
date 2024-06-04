"""Temperature helpers for Home Assistant."""

from __future__ import annotations

from numbers import Number

from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter


def display_temp(
    hass: HomeAssistant, temperature: float | None, unit: str, precision: float
) -> float | None:
    """Convert temperature into preferred units/precision for display."""
    temperature_unit = unit
    ha_unit = hass.config.units.temperature_unit

    if temperature is None:
        return temperature

    # If the temperature is not a number this can cause issues
    # with Polymer components, so bail early there.
    if not isinstance(temperature, Number):
        raise TypeError(f"Temperature is not a number: {temperature}")

    if temperature_unit != ha_unit:
        temperature = TemperatureConverter.converter_factory(temperature_unit, ha_unit)(
            temperature
        )

    # Round in the units appropriate
    if precision == PRECISION_HALVES:
        return round(temperature * 2) / 2.0
    if precision == PRECISION_TENTHS:
        return round(temperature, 1)
    # Integer as a fall back (PRECISION_WHOLE)
    return round(temperature)
