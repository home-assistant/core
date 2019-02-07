"""
Support for Meteo France weather forecast.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.meteo_france/
"""

import logging
import datetime

import voluptuous as vol

from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS)
from homeassistant.util import Throttle
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['meteofrance==0.2.8']
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'meteo_france'
SCAN_INTERVAL = datetime.timedelta(minutes=5)
CONF_ATTRIBUTION = "Data provided by Météo-France"
CONF_POSTAL_CODE = 'postal_code'
DEFAULT_WEATHER_CARD = True
DATA_METEO_FRANCE = 'data_meteo_france'

SENSOR_TYPES = {
    'rain_chance': ['Rain chance', '%'],
    'freeze_chance': ['Freeze chance', '%'],
    'thunder_chance': ['Thunder chance', '%'],
    'snow_chance': ['Snow chance', '%'],
    'weather': ['Weather', None],
    'wind_speed': ['Wind Speed', 'km/h'],
    'next_rain': ['Next rain', 'min'],
    'temperature': ['Temperature', TEMP_CELSIUS],
    'uv': ['UV', None],
}

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

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS):
            vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    })])
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Meteo-France component."""
    hass.data[DATA_METEO_FRANCE] = {}

    for location in config[DOMAIN]:

        postal_code = location[CONF_POSTAL_CODE]

        from meteofrance.client import meteofranceClient, meteofranceError

        try:
            client = meteofranceClient(postal_code)
        except meteofranceError as exp:
            _LOGGER.error(exp)
            return

        hass.data[DATA_METEO_FRANCE][postal_code] = MeteoFranceUpdater(client)

        if CONF_MONITORED_CONDITIONS in location:
            monitored_conditions = location[CONF_MONITORED_CONDITIONS]
            load_platform(
                hass,
                'sensor',
                DOMAIN,
                {CONF_POSTAL_CODE: postal_code,
                 CONF_MONITORED_CONDITIONS: monitored_conditions},
                config)

        load_platform(
            hass,
            'weather',
            DOMAIN,
            {CONF_POSTAL_CODE: postal_code},
            config)

    return True


class MeteoFranceUpdater:
    """Update data from Meteo-France."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client
        self.update()

    def get_data(self):
        """Get the latest data from Meteo-France."""
        return self._client.get_data()

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Meteo-France."""
        from meteofrance.client import meteofranceError
        try:
            self._client.update()
        except meteofranceError as exp:
            _LOGGER.error(exp)
