"""
homeassistant.helpers.temperature
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Methods to help handle temperature in Home Assistant.
"""

from homeassistant.const import TEMP_CELCIUS
import homeassistant.util.temperature as temp_util


def convert(temperature, unit, to_unit):
    """ Converts temperature to correct unit. """
    if unit == to_unit or unit is None or to_unit is None:
        return temperature
    elif unit == TEMP_CELCIUS:
        return temp_util.celcius_to_fahrenheit(temperature)

    return temp_util.fahrenheit_to_celcius(temperature)
