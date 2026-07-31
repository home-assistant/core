"""Helper to test significant Weather state changes."""

from typing import Any

from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import (
    check_absolute_change,
    check_valid_float,
)

from .const import WeatherEntityStateAttribute

SIGNIFICANT_ATTRIBUTES: set[str] = {
    WeatherEntityStateAttribute.APPARENT_TEMPERATURE,
    WeatherEntityStateAttribute.CLOUD_COVERAGE,
    WeatherEntityStateAttribute.DEW_POINT,
    WeatherEntityStateAttribute.HUMIDITY,
    WeatherEntityStateAttribute.OZONE,
    WeatherEntityStateAttribute.PRESSURE,
    WeatherEntityStateAttribute.TEMPERATURE,
    WeatherEntityStateAttribute.UV_INDEX,
    WeatherEntityStateAttribute.VISIBILITY,
    WeatherEntityStateAttribute.WIND_BEARING,
    WeatherEntityStateAttribute.WIND_GUST_SPEED,
    WeatherEntityStateAttribute.WIND_SPEED,
}

VALID_CARDINAL_DIRECTIONS: list[str] = [
    "n",
    "nne",
    "ne",
    "ene",
    "e",
    "ese",
    "se",
    "sse",
    "s",
    "ssw",
    "sw",
    "wsw",
    "w",
    "wnw",
    "nw",
    "nnw",
]


def _cardinal_to_degrees(value: str | float | None) -> int | float | None:
    """Translate a cardinal direction into azimuth angle (degrees)."""
    if not isinstance(value, str):
        return value

    try:
        return float(360 / 16 * VALID_CARDINAL_DIRECTIONS.index(value.lower()))
    except ValueError:
        return None


@callback
def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs: Any,
) -> bool | None:
    """Test if state significantly changed."""
    # state changes are always significant
    if old_state != new_state:
        return True

    old_attrs_s = set(
        {k: v for k, v in old_attrs.items() if k in SIGNIFICANT_ATTRIBUTES}.items()
    )
    new_attrs_s = set(
        {k: v for k, v in new_attrs.items() if k in SIGNIFICANT_ATTRIBUTES}.items()
    )
    changed_attrs: set[str] = {item[0] for item in old_attrs_s ^ new_attrs_s}

    for attr_name in changed_attrs:
        old_attr_value = old_attrs.get(attr_name)
        new_attr_value = new_attrs.get(attr_name)
        absolute_change: float | None = None
        if attr_name == WeatherEntityStateAttribute.WIND_BEARING:
            old_attr_value = _cardinal_to_degrees(old_attr_value)
            new_attr_value = _cardinal_to_degrees(new_attr_value)

        if new_attr_value is None or not check_valid_float(new_attr_value):
            # New attribute value is invalid, ignore it
            continue

        if old_attr_value is None or not check_valid_float(old_attr_value):
            # Old attribute value was invalid, we should report again
            return True

        if attr_name in (
            WeatherEntityStateAttribute.APPARENT_TEMPERATURE,
            WeatherEntityStateAttribute.DEW_POINT,
            WeatherEntityStateAttribute.TEMPERATURE,
        ):
            if (
                unit := new_attrs.get(WeatherEntityStateAttribute.TEMPERATURE_UNIT)
            ) is not None and unit == UnitOfTemperature.FAHRENHEIT:
                absolute_change = 1.0
            else:
                absolute_change = 0.5

        if attr_name in (
            WeatherEntityStateAttribute.WIND_GUST_SPEED,
            WeatherEntityStateAttribute.WIND_SPEED,
        ):
            if (
                unit := new_attrs.get(WeatherEntityStateAttribute.WIND_SPEED_UNIT)
            ) is None or unit in (
                UnitOfSpeed.KILOMETERS_PER_HOUR,
                UnitOfSpeed.MILES_PER_HOUR,  # 1km/h = 0.62mi/s
                UnitOfSpeed.FEET_PER_SECOND,  # 1km/h = 0.91ft/s
            ):
                absolute_change = 1.0
            elif unit == UnitOfSpeed.METERS_PER_SECOND:  # 1km/h = 0.277m/s
                absolute_change = 0.5

        if attr_name in (
            WeatherEntityStateAttribute.CLOUD_COVERAGE,  # range 0-100%
            WeatherEntityStateAttribute.HUMIDITY,  # range 0-100%
            WeatherEntityStateAttribute.OZONE,  # range ~20-100ppm
            WeatherEntityStateAttribute.VISIBILITY,  # range 0-240km (150mi)
            WeatherEntityStateAttribute.WIND_BEARING,  # range 0-359°
        ):
            absolute_change = 1.0

        if attr_name == WeatherEntityStateAttribute.UV_INDEX:  # range 1-11
            absolute_change = 0.1

        if (
            attr_name == WeatherEntityStateAttribute.PRESSURE
        ):  # local variation of around 100 hpa
            if (
                unit := new_attrs.get(WeatherEntityStateAttribute.PRESSURE_UNIT)
            ) is None or unit in (
                UnitOfPressure.HPA,
                UnitOfPressure.MBAR,  # 1hPa = 1mbar
                UnitOfPressure.MMHG,  # 1hPa = 0.75mmHg
            ):
                absolute_change = 1.0
            elif unit == UnitOfPressure.INHG:  # 1hPa = 0.03inHg
                absolute_change = 0.05

        # check for significant attribute value change
        if absolute_change is not None:
            if check_absolute_change(old_attr_value, new_attr_value, absolute_change):
                return True

    # no significant attribute change detected
    return False
