"""Temperature helpers for Home Assistant."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import Precision
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter


def display_temp(
    hass: HomeAssistant, temperature: float | None, unit: str, precision: Precision
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

    # Requiring the steps to be of type int means that any precision used must be of the form "1/n" for an integer "n". This dict maps the values "1/n" to "n".
    steps: dict[Precision, int] = {
        Precision.WHOLE: 1,
        Precision.HALVES: 2,
        Precision.TENTHS: 10,
    }

    # Integer as a fall back (PRECISION_WHOLE)
    precision = precision if precision else Precision.WHOLE

    try:
        step = steps[precision]
    except KeyError as e:
        raise ValueError(
            f"Precision not in [{', '.join(map(str, Precision))}]: {precision}"
        ) from e

    temperature = round(temperature * step) / step

    return temperature
