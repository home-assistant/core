"""
homeassistant.components.weather.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that offers fake meteorological data.
"""
from homeassistant.components.weather import WeatherCondition
from homeassistant.const import TEMP_CELCIUS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo weather conditions. """
    add_devices([
        DemoWeatherCondition('temperature', 21, TEMP_CELCIUS),
        DemoWeatherCondition('humidity', 68, '%')
    ])


# pylint: disable=too-many-arguments
class DemoWeatherCondition(WeatherCondition):
    """ Represents a weather condition. """

    def __init__(self, type, value, unit_of_measurement):
        self.type = type
        self._name = type.title()
        self._value = value
        self._unit_of_measurement = unit_of_measurement

    @property
    def should_poll(self):
        """ No polling needed for a demo weather condition. """
        return False

    @property
    def name(self):
        """ Returns the name. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return self._unit_of_measurement

    @property
    def weather_temperature(self):
        """ Returns the temperature. """
        return self._value

    @property
    def weather_humidity(self):
        """ Returns the humidity. """
        return self._value
