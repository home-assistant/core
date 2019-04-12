"""Support for Meteo-France weather data."""
import datetime
import logging

import voluptuous as vol

from homeassistant.const import CONF_MONITORED_CONDITIONS, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

REQUIREMENTS = ['meteofrance==0.3.4']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Météo-France"

CONF_CITY = 'city'

DATA_METEO_FRANCE = 'data_meteo_france'
DEFAULT_WEATHER_CARD = True
DOMAIN = 'meteo_france'

SCAN_INTERVAL = datetime.timedelta(minutes=5)

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
    'lightning-rainy': ['Pluie orageuses', 'Pluies orageuses',
                        'Averses orageuses'],
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


def has_all_unique_cities(value):
    """Validate that all cities are unique."""
    cities = [location[CONF_CITY] for location in value]
    vol.Schema(vol.Unique())(cities)
    return value


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_CITY): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS):
            vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    })], has_all_unique_cities)
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Meteo-France component."""
    hass.data[DATA_METEO_FRANCE] = {}

    for location in config[DOMAIN]:

        city = location[CONF_CITY]

        from meteofrance.client import meteofranceClient, meteofranceError

        try:
            client = meteofranceClient(city)
        except meteofranceError as exp:
            _LOGGER.error(exp)
            return

        client.need_rain_forecast = bool(
            CONF_MONITORED_CONDITIONS in location and 'next_rain' in
            location[CONF_MONITORED_CONDITIONS])

        hass.data[DATA_METEO_FRANCE][city] = MeteoFranceUpdater(client)
        hass.data[DATA_METEO_FRANCE][city].update()

        if CONF_MONITORED_CONDITIONS in location:
            monitored_conditions = location[CONF_MONITORED_CONDITIONS]
            load_platform(
                hass, 'sensor', DOMAIN, {
                    CONF_CITY: city,
                    CONF_MONITORED_CONDITIONS: monitored_conditions}, config)

        load_platform(hass, 'weather', DOMAIN, {CONF_CITY: city}, config)

    return True


class MeteoFranceUpdater:
    """Update data from Meteo-France."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client

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
