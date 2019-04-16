"""Support for Meteo-France weather service."""
from datetime import datetime, timedelta
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME, WeatherEntity)
from homeassistant.const import TEMP_CELSIUS

from . import ATTRIBUTION, CONDITION_CLASSES, CONF_CITY, DATA_METEO_FRANCE

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Meteo-France weather platform."""
    if discovery_info is None:
        return

    city = discovery_info[CONF_CITY]
    client = hass.data[DATA_METEO_FRANCE][city]

    add_entities([MeteoFranceWeather(client)], True)


class MeteoFranceWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, client):
        """Initialise the platform with a data instance and station name."""
        self._client = client
        self._data = {}

    def update(self):
        """Update current conditions."""
        self._client.update()
        self._data = self._client.get_data()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._data['name']

    @property
    def condition(self):
        """Return the current condition."""
        return self.format_condition(self._data['weather'])

    @property
    def temperature(self):
        """Return the temperature."""
        return self._data['temperature']

    @property
    def humidity(self):
        """Return the humidity."""
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._data['wind_speed']

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._data['wind_bearing']

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast."""
        reftime = datetime.now().replace(hour=12, minute=00)
        reftime += timedelta(hours=24)
        forecast_data = []
        for key in self._data['forecast']:
            value = self._data['forecast'][key]
            data_dict = {
                ATTR_FORECAST_TIME: reftime.isoformat(),
                ATTR_FORECAST_TEMP: int(value['max_temp']),
                ATTR_FORECAST_TEMP_LOW: int(value['min_temp']),
                ATTR_FORECAST_CONDITION:
                    self.format_condition(value['weather'])
            }
            reftime = reftime + timedelta(hours=24)
            forecast_data.append(data_dict)
        return forecast_data

    @staticmethod
    def format_condition(condition):
        """Return condition from dict CONDITION_CLASSES."""
        for key, value in CONDITION_CLASSES.items():
            if condition in value:
                return key
        return condition
