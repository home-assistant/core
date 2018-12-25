"""
Sensor support for AEMET (Agencia Estatal de Metereología) data service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.aemet/
"""

from datetime import timedelta
from logging import getLogger

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY)
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY,
    CONF_MONITORED_CONDITIONS, CONF_NAME, HTTP_OK, LENGTH_CENTIMETERS,
    LENGTH_KILOMETERS, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['python-aemet==0.1.2']

_LOGGER = getLogger(__name__)

ATTR_ELEVATION = 'elevation'
ATTR_LAST_UPDATE = 'last_update'
ATTR_STATION_NAME = 'station_name'
ATTR_WEATHER_PRECIPITATION = 'precipitation'
ATTR_WEATHER_SNOW = 'snow'

CONF_ATTRIBUTION = 'Data provided by AEMET (Agencia Estatal de Meteorología)'
CONF_STATION_ID = 'station_id'

DEFAULT_NAME = 'AEMET'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_TYPES = {
    ATTR_WEATHER_TEMPERATURE: ['Temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    ATTR_WEATHER_HUMIDITY: ['Humidity', '%', 'mdi:water-percent'],
    ATTR_WEATHER_PRESSURE: ['Pressure', 'hPa', 'mdi:gauge'],
    ATTR_WEATHER_PRECIPITATION: ['Precipitation', 'mm', 'mdi:weather-pouring'],
    ATTR_WEATHER_SNOW: ['Snow', LENGTH_CENTIMETERS, 'mdi:snowflake'],
    ATTR_WEATHER_VISIBILITY: ['Visibility', LENGTH_KILOMETERS, 'mdi:eye'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    station_id = config.get(CONF_STATION_ID)

    aemet_data = AemetData(api_key=api_key, station_id=station_id)
    try:
        aemet_data.update()
    except (ValueError, TypeError) as err:
        _LOGGER.error("Received error from AEMET: %s", err)
        return False

    add_entities([AemetSensor(aemet_data, variable, name)
                  for variable in config[CONF_MONITORED_CONDITIONS]], True)


class AemetSensor(Entity):
    """Representation of a sensor in the AEMET service."""

    def __init__(self, aemet_data, variable, name):
        """Initialize the sensor."""
        self.aemet_data = aemet_data
        self.variable = variable
        self.client_name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self.variable)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.aemet_data.get_data(self.variable)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self.variable][1]

    @property
    def icon(self):
        """Return sensor specific icon."""
        return SENSOR_TYPES[self.variable][2]

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_STATION_NAME: self.aemet_data.get_data(ATTR_STATION_NAME),
            ATTR_LATITUDE: self.aemet_data.get_data(ATTR_LATITUDE),
            ATTR_LONGITUDE: self.aemet_data.get_data(ATTR_LONGITUDE),
            ATTR_ELEVATION: self.aemet_data.get_data(ATTR_ELEVATION),
            ATTR_LAST_UPDATE: self.aemet_data.get_data(ATTR_LAST_UPDATE),
        }

    def update(self):
        """Delegate update to data class."""
        self.aemet_data.update()


class AemetData:
    """Get the lastest data and updates the states."""

    API_URL_BASE = 'https://opendata.aemet.es/opendata/api'
    API_STATION_ENDPOINT = '/observacion/convencional/datos/estacion/{}'

    def __init__(self, api_key, station_id):
        """Initialize the data object."""
        from aemet import Aemet

        self._station_id = station_id
        self._aemet_api = Aemet(api_key=api_key)
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        try:
            last_update = self._aemet_api.get_observacion_convencional(
                estacion=self._station_id,
                raw=True
            )
            self.set_data(last_update)

        except (ValueError, TypeError) as err:
            _LOGGER.error("Received error from AEMET: %s", err)

    def set_data(self, record):
        """Set data using the last record from API."""
        state = {}
        if 'lon' in record:
            state[ATTR_LONGITUDE] = record['lon']
        if 'lat' in record:
            state[ATTR_LATITUDE] = record['lat']
        if 'alt' in record:
            state[ATTR_ELEVATION] = record['alt']
        if 'ubi' in record:
            state[ATTR_STATION_NAME] = record['ubi']
        if 'prec' in record:
            state[ATTR_WEATHER_PRECIPITATION] = record['prec']
        if 'pres' in record:
            state[ATTR_WEATHER_PRESSURE] = record['pres']
        if 'ta' in record:
            state[ATTR_WEATHER_TEMPERATURE] = record['ta']
        if 'hr' in record:
            state[ATTR_WEATHER_HUMIDITY] = record['hr']
        if 'fint' in record:
            state[ATTR_LAST_UPDATE] = record['fint']
        if 'vis' in record:
            state[ATTR_WEATHER_VISIBILITY] = record['vis']
        if 'nieve' in record:
            state[ATTR_WEATHER_SNOW] = record['nieve']
        self.data = state

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)
