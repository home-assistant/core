"""Methods to help handle temperature in Home Assistant."""
import homeassistant.util.temperature as temp_util
from homeassistant.const import TEMP_CELSIUS


def convert(temperature, unit, to_unit):
    """Convert temperature to correct unit."""
    if unit == to_unit or unit is None or to_unit is None:
        return temperature
    elif unit == TEMP_CELSIUS:
        return temp_util.celsius_to_fahrenheit(temperature)

    return temp_util.fahrenheit_to_celsius(temperature)
