"""Speed helpers for Home Assistant."""
from numbers import Number

from homeassistant.core import HomeAssistant
from homeassistant.util.speed import convert as convert_speed


def display_speed(hass: HomeAssistant, speed: float, unit: str,
                  precision: float) -> float:
    """Convert sped into preferred units for display purposes."""
    speed_unit = unit
    ha_unit = hass.config.units.speed_unit

    if speed is None:
        return speed

    # If the speed is not a number this can cause issues
    # with Polymer components, so bail early there.
    if not isinstance(speed, Number):
        raise TypeError(
            "Speed is not a number: {}".format(speed))

    if speed_unit != ha_unit:
        speed = convert_speed(
            speed, speed_unit, ha_unit)

    # Round in the units appropriate
    if precision == 0.5:
        return round(speed * 2) / 2.0
    elif precision == 0.1:
        return round(speed, 1)
    # Integer as a fall back (PRECISION_WHOLE)
    return round(speed)
