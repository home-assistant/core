"""
homeassistant.components.weather
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Weather component that handles meteorological data for your location.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/weather/
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []

DOMAIN = "weather"
ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup(hass, config):
    """ Setup the weather service. """

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component.setup(config)

    return True


# pylint: disable=no-member, no-self-use, too-many-return-statements
class WeatherCondition(Entity):
    """ Represents a weather condition. """

    @property
    def weather_condition(self):
        """ Returns the weather condition. """
        return None

    @property
    def weather_temperature(self):
        """ Returns the temperature. """
        return None

    @property
    def weather_pressure(self):
        """ Returns the pressure. """
        return None

    @property
    def weather_humidity(self):
        """ Returns the humidity. """
        return None

    @property
    def weather_wind_speed(self):
        """ Returns the wind speed. """
        return None

    @property
    def weather_wind_bearing(self):
        """ Returns the wind bearing. """
        return None

    @property
    def weather_ozone(self):
        """ Returns the ozone level. """
        return None

    @property
    def condition_state_attributes(self):
        """ Returns condition specific state attributes. """
        return None

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return None

    @property
    def unit_of_measurement(self):
        """ Unit of measurement this condition expresses itself in. """
        return None

    @property
    def state(self):
        """ Returns the current state. """
        if self.type == 'condition' or self.type == 'summary' \
                or self.type == 'weather':
            return self.weather_condition
        elif self.type == 'temperature':
            return self.weather_temperature
        elif self.type == 'pressure':
            return self.weather_pressure
        elif self.type == 'humidity':
            return self.weather_humidity
        elif self.type == 'wind_speed':
            return self.weather_wind_speed
        elif self.type == 'wind_bearing':
            return self.weather_wind_bearing
        elif self.type == 'ozone':
            return self.weather_ozone
        else:
            return STATE_UNKNOWN
