"""Temperature helpers for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
from math import ceil, floor
from numbers import Number

from homeassistant.const import Precision, RoundMode
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter


def display_temp(
    hass: HomeAssistant,
    temperature: float | None,
    unit: str,
    precision: Precision,
    round_mode: RoundMode = RoundMode.NEAREST,
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

    round_funcs: dict[RoundMode, Callable[[float], int]] = {
        # "nearest" requires a lambda because function "round" has 2 arguments, so else types do not match.
        # This is despite the fact that the second argument to "round" has a default value, and thus "round" can be called with just 1 argument.
        RoundMode.NEAREST: lambda x: round(x, None),
        RoundMode.DOWN: floor,
        RoundMode.UP: ceil,
    }

    # Requiring the steps to be of type int means that any precision used must be of the form "1/n" for an integer "n". This dict maps the values "1/n" to "n".
    steps: dict[Precision, int] = {
        Precision.WHOLE: 1,
        Precision.HALVES: 2,
        Precision.TENTHS: 10,
    }

    # Integer as a fall back (PRECISION_WHOLE)
    precision = precision if precision else Precision.WHOLE

    try:
        round_func = round_funcs[round_mode]
    except KeyError as e:
        raise ValueError(
            f"RoundMode not in [{', '.join(map(str, RoundMode))}]: {round_mode}"
        ) from e

    try:
        step = steps[precision]
    except KeyError as e:
        raise ValueError(
            f"Precision not in [{', '.join(map(str, Precision))}]: {precision}"
        ) from e

    temperature = round_func(temperature * step) / step

    return temperature
