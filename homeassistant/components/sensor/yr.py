"""
Support for Yr.no weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.yr/
"""
import asyncio
from datetime import timedelta
import logging
from random import randrange
from xml.parsers.expat import ExpatError

import async_timeout
import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_ELEVATION, CONF_MONITORED_CONDITIONS,
    ATTR_ATTRIBUTION)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_utc_time_change)
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['xmltodict==0.11.0']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Weather forecast from yr.no, delivered by the Norwegian " \
                   "Meteorological Institute and the NRK."

# Sensor types are defined like so:
SENSOR_TYPES = {
    'symbol': ['Symbol', None],
    'precipitation': ['Precipitation', 'mm'],
    'temperature': ['Temperature', '°C'],
    'windSpeed': ['Wind speed', 'm/s'],
    'windGust': ['Wind gust', 'm/s'],
    'pressure': ['Pressure', 'hPa'],
    'windDirection': ['Wind direction', '°'],
    'humidity': ['Humidity', '%'],
    'fog': ['Fog', '%'],
    'cloudiness': ['Cloudiness', '%'],
    'lowClouds': ['Low clouds', '%'],
    'mediumClouds': ['Medium clouds', '%'],
    'highClouds': ['High clouds', '%'],
    'dewpointTemperature': ['Dewpoint temperature', '°C'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['symbol']): vol.All(
        cv.ensure_list, vol.Length(min=1), [vol.In(SENSOR_TYPES.keys())]),
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_ELEVATION): vol.Coerce(int),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Yr.no sensor."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    elevation = config.get(CONF_ELEVATION, hass.config.elevation or 0)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    coordinates = {'lat': str(latitude),
                   'lon': str(longitude),
                   'msl': str(elevation)}

    dev = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        dev.append(YrSensor(sensor_type))
    async_add_devices(dev)

    weather = YrData(hass, coordinates, dev)
    # Update weather on the hour, spread seconds
    async_track_utc_time_change(
        hass, weather.async_update, minute=randrange(1, 10),
        second=randrange(0, 59))
    yield from weather.async_update()


class YrSensor(Entity):
    """Representation of an Yr.no sensor."""

    def __init__(self, sensor_type):
        """Initialize the sensor."""
        self.client_name = 'yr'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):  # pylint: disable=no-self-use
        """No polling needed."""
        return False

    @property
    def entity_picture(self):
        """Weather symbol if type is symbol."""
        if self.type != 'symbol':
            return None
        return "//api.met.no/weatherapi/weathericon/1.1/" \
               "?symbol={0};content_type=image/png".format(self._state)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement


class YrData(object):
    """Get the latest data and updates the states."""

    def __init__(self, hass, coordinates, devices):
        """Initialize the data object."""
        self._url = 'https://aa015h6buqvih86i1.api.met.no/'\
                    'weatherapi/locationforecast/1.9/'
        self._urlparams = coordinates
        self._nextrun = None
        self.devices = devices
        self.data = {}
        self.hass = hass

    @asyncio.coroutine
    def async_update(self, *_):
        """Get the latest data from yr.no."""
        import xmltodict

        def try_again(err: str):
            """Retry in 15 minutes."""
            _LOGGER.warning('Retrying in 15 minutes: %s', err)
            self._nextrun = None
            nxt = dt_util.utcnow() + timedelta(minutes=15)
            if nxt.minute >= 15:
                async_track_point_in_utc_time(self.hass, self.async_update,
                                              nxt)

        if self._nextrun is None or dt_util.utcnow() >= self._nextrun:
            try:
                websession = async_get_clientsession(self.hass)
                with async_timeout.timeout(10, loop=self.hass.loop):
                    resp = yield from websession.get(
                        self._url, params=self._urlparams)
                if resp.status != 200:
                    try_again('{} returned {}'.format(resp.url, resp.status))
                    return
                text = yield from resp.text()

            except (asyncio.TimeoutError, aiohttp.ClientError) as err:
                try_again(err)
                return

            try:
                self.data = xmltodict.parse(text)['weatherdata']
                model = self.data['meta']['model']
                if '@nextrun' not in model:
                    model = model[0]
                self._nextrun = dt_util.parse_datetime(model['@nextrun'])
            except (ExpatError, IndexError) as err:
                try_again(err)
                return

        now = dt_util.utcnow()

        tasks = []
        # Update all devices
        for dev in self.devices:
            # Find sensor
            for time_entry in self.data['product']['time']:
                valid_from = dt_util.parse_datetime(time_entry['@from'])
                valid_to = dt_util.parse_datetime(time_entry['@to'])
                new_state = None

                loc_data = time_entry['location']

                if dev.type not in loc_data or now >= valid_to:
                    continue

                if dev.type == 'precipitation' and valid_from < now:
                    new_state = loc_data[dev.type]['@value']
                    break
                elif dev.type == 'symbol' and valid_from < now:
                    new_state = loc_data[dev.type]['@number']
                    break
                elif dev.type in ('temperature', 'pressure', 'humidity',
                                  'dewpointTemperature'):
                    new_state = loc_data[dev.type]['@value']
                    break
                elif dev.type in ('windSpeed', 'windGust'):
                    new_state = loc_data[dev.type]['@mps']
                    break
                elif dev.type == 'windDirection':
                    new_state = float(loc_data[dev.type]['@deg'])
                    break
                elif dev.type in ('fog', 'cloudiness', 'lowClouds',
                                  'mediumClouds', 'highClouds'):
                    new_state = loc_data[dev.type]['@percent']
                    break

            # pylint: disable=protected-access
            if new_state != dev._state:
                dev._state = new_state
                tasks.append(dev.async_update_ha_state())

        if tasks:
            yield from asyncio.wait(tasks, loop=self.hass.loop)
