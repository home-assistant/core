"""Define sensors for AirVisual air quality data."""

import asyncio
from logging import getLogger
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_API_KEY, CONF_LATITUDE,
                                 CONF_LONGITUDE, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = getLogger(__name__)
REQUIREMENTS = ['pyairvisual==0.1.0']

ATTR_CITY = 'city'
ATTR_COUNTRY = 'country'
ATTR_POLLUTANT_SYMBOL = 'pollutant_symbol'
ATTR_POLLUTANT_UNIT = 'pollutant_unit'
ATTR_STATE = 'state'
ATTR_TIMESTAMP = 'timestamp'

CONF_RADIUS = 'radius'

MASS_PARTS_PER_MILLION = 'ppm'
MASS_PARTS_PER_BILLION = 'ppb'
VOLUME_MICROGRAMS_PER_CUBIC_METER = 'µg/m3'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

POLLUTANT_LEVEL_MAPPING = [{
    'label': 'Good',
    'minimum': 0,
    'maximum': 50
}, {
    'label': 'Moderate',
    'minimum': 51,
    'maximum': 100
}, {
    'label': 'Unhealthy for Sensitive Groups',
    'minimum': 101,
    'maximum': 150
}, {
    'label': 'Unhealthy',
    'minimum': 151,
    'maximum': 200
}, {
    'label': 'Very Unhealthy',
    'minimum': 201,
    'maximum': 300
}, {
    'label': 'Hazardous',
    'minimum': 301,
    'maximum': 10000
}]
POLLUTANT_MAPPING = {
    'co': {
        'label': 'Carbon Monoxide',
        'unit': MASS_PARTS_PER_MILLION
    },
    'n2': {
        'label': 'Nitrogen Dioxide',
        'unit': MASS_PARTS_PER_BILLION
    },
    'o3': {
        'label': 'Ozone',
        'unit': MASS_PARTS_PER_BILLION
    },
    'p1': {
        'label': 'PM10',
        'unit': VOLUME_MICROGRAMS_PER_CUBIC_METER
    },
    'p2': {
        'label': 'PM2.5',
        'unit': VOLUME_MICROGRAMS_PER_CUBIC_METER
    },
    's2': {
        'label': 'Sulfur Dioxide',
        'unit': MASS_PARTS_PER_BILLION
    }
}

SENSOR_LOCALES = {'cn': 'Chinese', 'us': 'U.S.'}
SENSOR_TYPES = [
    ('AirPollutionLevelSensor', 'Air Pollution Level', 'mdi:scale'),
    ('AirQualityIndexSensor', 'Air Quality Index', 'mdi:format-list-numbers'),
    ('MainPollutantSensor', 'Main Pollutant', 'mdi:chemical-weapon'),
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY):
    cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
    vol.All(cv.ensure_list, [vol.In(SENSOR_LOCALES)]),
    vol.Optional(CONF_LATITUDE):
    cv.latitude,
    vol.Optional(CONF_LONGITUDE):
    cv.longitude,
    vol.Optional(CONF_RADIUS, default=1000):
    cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Configure the platform and add the sensors."""
    import pyairvisual as pav

    api_key = config.get(CONF_API_KEY)
    _LOGGER.debug('AirVisual API Key: %s', api_key)

    monitored_locales = config.get(CONF_MONITORED_CONDITIONS)
    _LOGGER.debug('Monitored Conditions: %s', monitored_locales)

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    _LOGGER.debug('AirVisual Latitude: %s', latitude)

    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    _LOGGER.debug('AirVisual Longitude: %s', longitude)

    radius = config.get(CONF_RADIUS)
    _LOGGER.debug('AirVisual Radius: %s', radius)

    data = AirVisualData(pav.Client(api_key), latitude, longitude, radius)

    sensors = []
    for locale in monitored_locales:
        for sensor_class, name, icon in SENSOR_TYPES:
            sensors.append(globals()[sensor_class](data, name, icon, locale))

    async_add_devices(sensors, True)


class AirVisualBaseSensor(Entity):
    """Define a base class for all of our sensors."""

    def __init__(self, data, name, icon, locale):
        """Initialize."""
        self._data = data
        self._icon = icon
        self._locale = locale
        self._name = name
        self._state = None
        self._unit = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._data:
            return {
                ATTR_ATTRIBUTION: 'AirVisual©',
                ATTR_CITY: self._data.city,
                ATTR_COUNTRY: self._data.country,
                ATTR_STATE: self._data.state,
                ATTR_TIMESTAMP: self._data.pollution_info.get('ts')
            }

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return '{0} {1}'.format(SENSOR_LOCALES[self._locale], self._name)

    @property
    def state(self):
        """Return the state."""
        return self._state

    @asyncio.coroutine
    def async_update(self):
        """Update the status of the sensor."""
        _LOGGER.debug('updating sensor: %s', self._name)
        self._data.update()


class AirPollutionLevelSensor(AirVisualBaseSensor):
    """Define a sensor to measure air pollution level."""

    @asyncio.coroutine
    def async_update(self):
        """Update the status of the sensor."""
        yield from super().async_update()
        aqi = self._data.pollution_info.get('aqi{0}'.format(self._locale))

        try:
            [level] = [
                i for i in POLLUTANT_LEVEL_MAPPING
                if i['minimum'] <= aqi <= i['maximum']
            ]
            self._state = level.get('label')
        except ValueError:
            self._state = None


class AirQualityIndexSensor(AirVisualBaseSensor):
    """Define a sensor to measure AQI."""

    @asyncio.coroutine
    def async_update(self):
        """Update the status of the sensor."""
        yield from super().async_update()
        self._state = self._data.pollution_info.get(
            'aqi{0}'.format(self._locale))


class MainPollutantSensor(AirVisualBaseSensor):
    """Define a sensor to the main pollutant of an area."""

    def __init__(self, data, name, icon, locale):
        """Initialize."""
        super().__init__(data, name, icon, locale)
        self._symbol = None
        self._unit = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._data:
            return {
                **super().device_state_attributes,
                **{
                    ATTR_POLLUTANT_SYMBOL: self._symbol,
                    ATTR_POLLUTANT_UNIT: self._unit
                }
            }

    @asyncio.coroutine
    def async_update(self):
        """Update the status of the sensor."""
        yield from super().async_update()
        symbol = self._data.pollution_info.get('main{0}'.format(self._locale))
        pollution_info = POLLUTANT_MAPPING.get(symbol, {})
        self._state = pollution_info.get('label')
        self._unit = pollution_info.get('unit')
        self._symbol = symbol


class AirVisualData(object):
    """Define an object to hold sensor data."""

    def __init__(self, client, latitude, longitude, radius):
        """Initialize."""
        self._city = None
        self._client = client
        self._country = None
        self._latitude = latitude
        self._longitude = longitude
        self._pollution_info = None
        self._radius = radius
        self._state = None

    @property
    def client(self):
        """Define a property to access the pyairvisual client."""
        return self._client

    @property
    def city(self):
        """Define a property to access the city."""
        return self._city

    @property
    def country(self):
        """Define a property to access the country."""
        return self._country

    @property
    def pollution_info(self):
        """Define a property to access the pollution information."""
        return self._pollution_info

    @property
    def state(self):
        """Define a property to access the state."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update with new AirVisual data."""
        import pyairvisual.exceptions as exceptions

        try:
            resp = self._client.nearest_city(self._latitude, self._longitude,
                                             self._radius).get('data')
            _LOGGER.debug('New data retrieved: %s', resp)

            self._city = resp.get('city')
            self._state = resp.get('state')
            self._country = resp.get('country')
            self._pollution_info = resp.get('current').get('pollution')
        except exceptions.HTTPError as exc_info:
            _LOGGER.error('Unable to update sensor data')
            _LOGGER.debug(exc_info)


# class AirVisualSensor(Entity):
#     """Define an object to represent the actual sensor."""

#     @property
#     def unit_of_measurement(self):
#         """Return the unit the value is expressed in."""
#         return getattr(self._data, 'main{0}_unit'.format(self._locale))
