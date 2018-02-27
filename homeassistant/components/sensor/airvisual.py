"""
Support for AirVisual air quality sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.airvisual/
"""
from logging import getLogger
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS, CONF_STATE,
    CONF_SHOW_ON_MAP, CONF_RADIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyairvisual==1.0.0']
_LOGGER = getLogger(__name__)

ATTR_CITY = 'city'
ATTR_COUNTRY = 'country'
ATTR_POLLUTANT_SYMBOL = 'pollutant_symbol'
ATTR_POLLUTANT_UNIT = 'pollutant_unit'
ATTR_REGION = 'region'

CONF_CITY = 'city'
CONF_COUNTRY = 'country'
CONF_ATTRIBUTION = "Data provided by AirVisual"

MASS_PARTS_PER_MILLION = 'ppm'
MASS_PARTS_PER_BILLION = 'ppb'
VOLUME_MICROGRAMS_PER_CUBIC_METER = 'µg/m3'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

SENSOR_TYPES = [
    ('AirPollutionLevelSensor', 'Air Pollution Level', 'mdi:scale'),
    ('AirQualityIndexSensor', 'Air Quality Index', 'mdi:format-list-numbers'),
    ('MainPollutantSensor', 'Main Pollutant', 'mdi:chemical-weapon'),
]

POLLUTANT_LEVEL_MAPPING = [
    {'label': 'Good', 'minimum': 0, 'maximum': 50},
    {'label': 'Moderate', 'minimum': 51, 'maximum': 100},
    {'label': 'Unhealthy for sensitive group', 'minimum': 101, 'maximum': 150},
    {'label': 'Unhealthy', 'minimum': 151, 'maximum': 200},
    {'label': 'Very Unhealthy', 'minimum': 201, 'maximum': 300},
    {'label': 'Hazardous', 'minimum': 301, 'maximum': 10000}
]

POLLUTANT_MAPPING = {
    'co': {'label': 'Carbon Monoxide', 'unit': MASS_PARTS_PER_MILLION},
    'n2': {'label': 'Nitrogen Dioxide', 'unit': MASS_PARTS_PER_BILLION},
    'o3': {'label': 'Ozone', 'unit': MASS_PARTS_PER_BILLION},
    'p1': {'label': 'PM10', 'unit': VOLUME_MICROGRAMS_PER_CUBIC_METER},
    'p2': {'label': 'PM2.5', 'unit': VOLUME_MICROGRAMS_PER_CUBIC_METER},
    's2': {'label': 'Sulfur Dioxide', 'unit': MASS_PARTS_PER_BILLION},
}

SENSOR_LOCALES = {'cn': 'Chinese', 'us': 'U.S.'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_LOCALES)]),
    vol.Optional(CONF_CITY): cv.string,
    vol.Optional(CONF_COUNTRY): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS, default=1000): cv.positive_int,
    vol.Optional(CONF_SHOW_ON_MAP, default=True): cv.boolean,
    vol.Optional(CONF_STATE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pyairvisual import Client

    classes = {
        'AirPollutionLevelSensor': AirPollutionLevelSensor,
        'AirQualityIndexSensor': AirQualityIndexSensor,
        'MainPollutantSensor': MainPollutantSensor
    }

    api_key = config.get(CONF_API_KEY)
    monitored_locales = config.get(CONF_MONITORED_CONDITIONS)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    radius = config.get(CONF_RADIUS)
    city = config.get(CONF_CITY)
    state = config.get(CONF_STATE)
    country = config.get(CONF_COUNTRY)
    show_on_map = config.get(CONF_SHOW_ON_MAP)

    if city and state and country:
        _LOGGER.debug(
            "Using city, state, and country: %s, %s, %s", city, state, country)
        location_id = ','.join((city, state, country))
        data = AirVisualData(
            Client(api_key), city=city, state=state, country=country,
            show_on_map=show_on_map)
    else:
        _LOGGER.debug(
            "Using latitude and longitude: %s, %s", latitude, longitude)
        location_id = ','.join((str(latitude), str(longitude)))
        data = AirVisualData(
            Client(api_key), latitude=latitude, longitude=longitude,
            radius=radius, show_on_map=show_on_map)

    data.update()

    sensors = []
    for locale in monitored_locales:
        for sensor_class, name, icon in SENSOR_TYPES:
            sensors.append(classes[sensor_class](
                data,
                name,
                icon,
                locale,
                location_id
            ))

    add_devices(sensors, True)


class AirVisualBaseSensor(Entity):
    """Define a base class for all of our sensors."""

    def __init__(self, data, name, icon, locale, entity_id):
        """Initialize the sensor."""
        self.data = data
        self._attrs = {}
        self._icon = icon
        self._locale = locale
        self._name = name
        self._state = None
        self._entity_id = entity_id
        self._unit = None

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        self._attrs.update({
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        })

        if self.data.show_on_map:
            self._attrs[ATTR_LATITUDE] = self.data.latitude
            self._attrs[ATTR_LONGITUDE] = self.data.longitude
        else:
            self._attrs['lati'] = self.data.latitude
            self._attrs['long'] = self.data.longitude

        return self._attrs

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


class AirPollutionLevelSensor(AirVisualBaseSensor):
    """Define a sensor to measure air pollution level."""

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_pollution_level'.format(self._entity_id)

    def update(self):
        """Update the status of the sensor."""
        self.data.update()

        aqi = self.data.pollution_info.get('aqi{0}'.format(self._locale))
        try:
            [level] = [
                i for i in POLLUTANT_LEVEL_MAPPING
                if i['minimum'] <= aqi <= i['maximum']
            ]
            self._state = level.get('label')
        except TypeError:
            self._state = None
        except ValueError:
            self._state = None


class AirQualityIndexSensor(AirVisualBaseSensor):
    """Define a sensor to measure AQI."""

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_aqi'.format(self._entity_id)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return 'AQI'

    def update(self):
        """Update the status of the sensor."""
        self.data.update()

        self._state = self.data.pollution_info.get(
            'aqi{0}'.format(self._locale))


class MainPollutantSensor(AirVisualBaseSensor):
    """Define a sensor to the main pollutant of an area."""

    def __init__(self, data, name, icon, locale, entity_id):
        """Initialize the sensor."""
        super().__init__(data, name, icon, locale, entity_id)
        self._symbol = None
        self._unit = None

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_main_pollutant'.format(self._entity_id)

    def update(self):
        """Update the status of the sensor."""
        self.data.update()

        symbol = self.data.pollution_info.get('main{0}'.format(self._locale))
        pollution_info = POLLUTANT_MAPPING.get(symbol, {})
        self._state = pollution_info.get('label')
        self._unit = pollution_info.get('unit')
        self._symbol = symbol

        self._attrs.update({
            ATTR_POLLUTANT_SYMBOL: self._symbol,
            ATTR_POLLUTANT_UNIT: self._unit
        })


class AirVisualData(object):
    """Define an object to hold sensor data."""

    def __init__(self, client, **kwargs):
        """Initialize the AirVisual data element."""
        self._client = client
        self.attrs = {}
        self.pollution_info = None

        self.city = kwargs.get(CONF_CITY)
        self.state = kwargs.get(CONF_STATE)
        self.country = kwargs.get(CONF_COUNTRY)

        self.latitude = kwargs.get(CONF_LATITUDE)
        self.longitude = kwargs.get(CONF_LONGITUDE)
        self._radius = kwargs.get(CONF_RADIUS)

        self.show_on_map = kwargs.get(CONF_SHOW_ON_MAP)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update with new AirVisual data."""
        from pyairvisual.exceptions import HTTPError

        try:
            if self.city and self.state and self.country:
                resp = self._client.city(
                    self.city, self.state, self.country).get('data')
                self.longitude, self.latitude = resp.get('location').get(
                    'coordinates')
            else:
                resp = self._client.nearest_city(
                    self.latitude, self.longitude, self._radius).get('data')
            _LOGGER.debug("New data retrieved: %s", resp)

            self.pollution_info = resp.get('current', {}).get('pollution', {})

            self.attrs = {
                ATTR_CITY: resp.get('city'),
                ATTR_REGION: resp.get('state'),
                ATTR_COUNTRY: resp.get('country')
            }
        except HTTPError as exc_info:
            _LOGGER.error("Unable to retrieve data on this location: %s",
                          self.__dict__)
            _LOGGER.debug(exc_info)
            self.pollution_info = {}
