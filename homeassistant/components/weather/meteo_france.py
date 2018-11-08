"""
Support for Meteo france weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.meteo_france/
"""
import logging
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP, ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers import config_validation as cv
# Reuse data and API logic from the sensor implementation
from homeassistant.components.sensor.meteo_france import \
    MeteoFranceUpdater, CONF_POSTAL_CODE, CONF_ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_POSTAL_CODE): cv.string,
})

CONDITION_CLASSES = {
    'clear-night': ['Nuit Claire'],
    'cloudy': ['Très nuageux'],
    'fog': ['Brume ou bancs de brouillard',
            'Brouillard', 'Brouillard givrant'],
    'hail': ['Risque de grêle'],
    'lightning': ["Risque d'orages", 'Orages'],
    'lightning-rainy': ['Pluie orageuses', 'Pluies orageuses'],
    'partlycloudy': ['Ciel voilé', 'Ciel voilé nuit', 'Éclaircies'],
    'pouring': ['Pluie forte'],
    'rainy': ['Bruine / Pluie faible', 'Bruine', 'Pluie faible',
              'Pluies éparses / Rares averses', 'Pluies éparses',
              'Rares averses', 'Pluie / Averses', 'Averses', 'Pluie'],
    'snowy': ['Neige / Averses de neige', 'Neige', 'Averses de neige',
              'Neige forte', 'Quelques flocons'],
    'snowy-rainy': ['Pluie et neige', 'Pluie verglaçante'],
    'sunny': ['Ensoleillé'],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Meteo-France weather platform."""
    postal_code = config[CONF_POSTAL_CODE]

    from meteofrance.client import meteofranceClient, meteofranceError

    try:
        meteofrance_client = meteofranceClient(postal_code)
    except meteofranceError as exp:
        _LOGGER.error(exp)
        return

    client = MeteoFranceUpdater(meteofrance_client)

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
        return self._data["name"]

    @property
    def condition(self):
        """Return the current condition."""
        return self._data["weather"]

    @property
    def condition_icon(self):
        """Return the current condition."""
        return self.format_condition(self._data["weather"])

    # Now implement the WeatherEntity interface
    @property
    def temperature(self):
        """Return the platform temperature."""
        return self._data["temperature"]

    @property
    def humidity(self):
        """Return the platform temperature."""
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def rain_forecast(self):
        """Return the 1 hour rain forecast."""
        return self._data["rain_forecast_text"]

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._data["wind_speed"]

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._data["wind_bearing"]

    @property
    def attribution(self):
        """Return the attribution."""
        return CONF_ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast."""
        reftime = datetime.now().replace(hour=12, minute=00)
        reftime += timedelta(hours=24)
        forecast_data = []
        for key in self._data["forecast"]:
            value = self._data["forecast"][key]
            data_dict = {
                ATTR_FORECAST_TIME: reftime.isoformat(),
                ATTR_FORECAST_TEMP: int(value['max_temp']),
                ATTR_FORECAST_TEMP_LOW: int(value['min_temp']),
                ATTR_FORECAST_CONDITION:
                    self.format_condition(value["weather"])
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
