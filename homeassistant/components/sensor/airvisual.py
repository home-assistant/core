"""
Support for AirVisual air quality sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.airvisual/
"""
from logging import getLogger
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL, CONF_STATE, CONF_SHOW_ON_MAP)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyairvisual==2.0.1']
_LOGGER = getLogger(__name__)

ATTR_CITY = 'city'
ATTR_COUNTRY = 'country'
ATTR_POLLUTANT_SYMBOL = 'pollutant_symbol'
ATTR_POLLUTANT_UNIT = 'pollutant_unit'
ATTR_REGION = 'region'

CONF_CITY = 'city'
CONF_COUNTRY = 'country'

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

MASS_PARTS_PER_MILLION = 'ppm'
MASS_PARTS_PER_BILLION = 'ppb'
VOLUME_MICROGRAMS_PER_CUBIC_METER = 'µg/m3'

SENSOR_TYPE_LEVEL = 'air_pollution_level'
SENSOR_TYPE_AQI = 'air_quality_index'
SENSOR_TYPE_POLLUTANT = 'main_pollutant'
SENSORS = [
    (SENSOR_TYPE_LEVEL, 'Air Pollution Level', 'mdi:scale', None),
    (SENSOR_TYPE_AQI, 'Air Quality Index', 'mdi:format-list-numbers', 'AQI'),
    (SENSOR_TYPE_POLLUTANT, 'Main Pollutant', 'mdi:chemical-weapon', None),
]

POLLUTANT_LEVEL_MAPPING = [{
    'label': 'Good',
    'minimum': 0,
    'maximum': 50
}, {
    'label': 'Moderate',
    'minimum': 51,
    'maximum': 100
}, {
    'label': 'Unhealthy for sensitive group',
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
    },
}

SENSOR_LOCALES = {'cn': 'Chinese', 'us': 'U.S.'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_LOCALES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_LOCALES)]),
    vol.Inclusive(CONF_CITY, 'city'): cv.string,
    vol.Inclusive(CONF_COUNTRY, 'city'): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coords'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coords'): cv.longitude,
    vol.Optional(CONF_SHOW_ON_MAP, default=True): cv.boolean,
    vol.Inclusive(CONF_STATE, 'city'): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        cv.time_period
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Configure the platform and add the sensors."""
    from pyairvisual import Client

    city = config.get(CONF_CITY)
    state = config.get(CONF_STATE)
    country = config.get(CONF_COUNTRY)

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    websession = aiohttp_client.async_get_clientsession(hass)

    if city and state and country:
        _LOGGER.debug(
            "Using city, state, and country: %s, %s, %s", city, state, country)
        location_id = ','.join((city, state, country))
        data = AirVisualData(
            Client(config[CONF_API_KEY], websession),
            city=city,
            state=state,
            country=country,
            show_on_map=config[CONF_SHOW_ON_MAP],
            scan_interval=config[CONF_SCAN_INTERVAL])
    else:
        _LOGGER.debug(
            "Using latitude and longitude: %s, %s", latitude, longitude)
        location_id = ','.join((str(latitude), str(longitude)))
        data = AirVisualData(
            Client(config[CONF_API_KEY], websession),
            latitude=latitude,
            longitude=longitude,
            show_on_map=config[CONF_SHOW_ON_MAP],
            scan_interval=config[CONF_SCAN_INTERVAL])

    await data.async_update()

    sensors = []
    for locale in config[CONF_MONITORED_CONDITIONS]:
        for kind, name, icon, unit in SENSORS:
            sensors.append(
                AirVisualSensor(
                    data, kind, name, icon, unit, locale, location_id))

    async_add_entities(sensors, True)


class AirVisualSensor(Entity):
    """Define an AirVisual sensor."""

    def __init__(self, airvisual, kind, name, icon, unit, locale, location_id):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._locale = locale
        self._location_id = location_id
        self._name = name
        self._state = None
        self._type = kind
        self._unit = unit
        self.airvisual = airvisual

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.airvisual.show_on_map:
            self._attrs[ATTR_LATITUDE] = self.airvisual.latitude
            self._attrs[ATTR_LONGITUDE] = self.airvisual.longitude
        else:
            self._attrs['lati'] = self.airvisual.latitude
            self._attrs['long'] = self.airvisual.longitude

        return self._attrs

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.airvisual.pollution_info)

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

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}_{2}'.format(
            self._location_id, self._locale, self._type)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_update(self):
        """Update the sensor."""
        await self.airvisual.async_update()
        data = self.airvisual.pollution_info

        if not data:
            return

        if self._type == SENSOR_TYPE_LEVEL:
            aqi = data['aqi{0}'.format(self._locale)]
            [level] = [
                i for i in POLLUTANT_LEVEL_MAPPING
                if i['minimum'] <= aqi <= i['maximum']
            ]
            self._state = level['label']
        elif self._type == SENSOR_TYPE_AQI:
            self._state = data['aqi{0}'.format(self._locale)]
        elif self._type == SENSOR_TYPE_POLLUTANT:
            symbol = data['main{0}'.format(self._locale)]
            self._state = POLLUTANT_MAPPING[symbol]['label']
            self._attrs.update({
                ATTR_POLLUTANT_SYMBOL: symbol,
                ATTR_POLLUTANT_UNIT: POLLUTANT_MAPPING[symbol]['unit']
            })


class AirVisualData:
    """Define an object to hold sensor data."""

    def __init__(self, client, **kwargs):
        """Initialize."""
        self._client = client
        self.city = kwargs.get(CONF_CITY)
        self.country = kwargs.get(CONF_COUNTRY)
        self.latitude = kwargs.get(CONF_LATITUDE)
        self.longitude = kwargs.get(CONF_LONGITUDE)
        self.pollution_info = {}
        self.show_on_map = kwargs.get(CONF_SHOW_ON_MAP)
        self.state = kwargs.get(CONF_STATE)

        self.async_update = Throttle(
            kwargs[CONF_SCAN_INTERVAL])(self._async_update)

    async def _async_update(self):
        """Update AirVisual data."""
        from pyairvisual.errors import AirVisualError

        try:
            if self.city and self.state and self.country:
                resp = await self._client.data.city(
                    self.city, self.state, self.country)
                self.longitude, self.latitude = resp['location']['coordinates']
            else:
                resp = await self._client.data.nearest_city(
                    self.latitude, self.longitude)

            _LOGGER.debug("New data retrieved: %s", resp)

            self.pollution_info = resp['current']['pollution']
        except (KeyError, AirVisualError) as err:
            if self.city and self.state and self.country:
                location = (self.city, self.state, self.country)
            else:
                location = (self.latitude, self.longitude)

            _LOGGER.error(
                "Can't retrieve data for location: %s (%s)", location,
                err)
            self.pollution_info = {}
