"""
Support for Buienradar.nl weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.buienradar/
"""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time)
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['buienradar==0.4']

_LOGGER = logging.getLogger(__name__)

# Supported sensor types:
SENSOR_TYPES = {
    'stationname': ['Stationname', None, None],
    'symbol': ['Symbol', None, None],
    'humidity': ['Humidity', '%', 'mdi:water-percent'],
    'temperature': ['Temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    'groundtemperature': ['Ground Temperature', TEMP_CELSIUS,
                          'mdi:thermometer'],
    'windspeed': ['Wind speed', 'm/s', 'mdi:weather-windy'],
    'windforce': ['Wind force', 'Bft', 'mdi:weather-windy'],
    'winddirection': ['Wind direction', '°', 'mdi:compass-outline'],
    'windazimuth': ['Wind direction azimuth', None, 'mdi:compass-outline'],
    'pressure': ['Pressure', 'hPa', 'mdi:gauge'],
    'visibility': ['Visibility', 'm', None],
    'windgust': ['Wind gust', 'm/s', 'mdi:weather-windy'],
    'precipitation': ['Precipitation', 'mm/h', 'mdi:weather-pouring'],
    'irradiance': ['Irradiance', 'W/m2', 'mdi:sunglasses'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=['symbol', 'temperature']): vol.All(
                     cv.ensure_list, vol.Length(min=1),
                     [vol.In(SENSOR_TYPES.keys())]),
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the buienradar sensor."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in HomeAssistant config")
        return False

    coordinates = {CONF_LATITUDE: float(latitude),
                   CONF_LONGITUDE: float(longitude)}

    dev = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        dev.append(BrSensor(sensor_type, config.get(CONF_NAME, 'br')))
    async_add_devices(dev)

    data = BrData(hass, coordinates, dev)
    # schedule the first update in 1 minute from now:
    _LOGGER.debug("Start running....")
    yield from data.schedule_update(1)


class BrSensor(Entity):
    """Representation of an Buienradar sensor."""

    def __init__(self, sensor_type, client_name):
        """Initialize the sensor."""
        self.client_name = client_name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._entity_picture = None
        self._attribution = None
        self._stationname = None

    def load_data(self, data):
        """Load the sensor with relevant data."""
        # Find sensor
        from buienradar.buienradar import (ATTRIBUTION, IMAGE,
                                           STATIONNAME, SYMBOL)

        self._attribution = data.get(ATTRIBUTION)
        self._stationname = data.get(STATIONNAME)
        if self.type == SYMBOL:
            # update weather symbol & status text
            new_state = data.get(self.type)
            img = data.get(IMAGE)

            # pylint: disable=protected-access
            if new_state != self._state or img != self._entity_picture:
                self._state = new_state
                self._entity_picture = img
                return True
        else:
            # update all other sensors
            new_state = data.get(self.type)
            # pylint: disable=protected-access
            if new_state != self._state:
                self._state = new_state
                return True

    @property
    def attribution(self):
        """Return the attribution."""
        return self._attribution

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
        from buienradar.buienradar import SYMBOL

        if self.type != SYMBOL:
            return None
        else:
            return self._entity_picture

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: self._attribution,
            SENSOR_TYPES['stationname'][0]: self._stationname,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return possible sensor specific icon."""
        return SENSOR_TYPES[self.type][2]


class BrData(object):
    """Get the latest data and updates the states."""

    def __init__(self, hass, coordinates, devices):
        """Initialize the data object."""
        self.devices = devices
        self.data = {}
        self.hass = hass
        self.coordinates = coordinates

    @asyncio.coroutine
    def update_devices(self):
        """Update all devices/sensors."""
        if self.devices:
            tasks = []
            # Update all devices
            for dev in self.devices:
                if dev.load_data(self.data):
                    tasks.append(dev.async_update_ha_state())

            if tasks:
                yield from asyncio.wait(tasks, loop=self.hass.loop)

    @asyncio.coroutine
    def schedule_update(self, minute=1):
        """Schedule an update after minute minutes."""
        _LOGGER.debug("Scheduling next update in %s minutes.", minute)
        nxt = dt_util.utcnow() + timedelta(minutes=minute)
        async_track_point_in_utc_time(self.hass, self.async_update,
                                      nxt)

    @asyncio.coroutine
    def get_data(self, url):
        """Load xmpl data from specified url."""
        from buienradar.buienradar import (CONTENT,
                                           MESSAGE, STATUS_CODE, SUCCESS)

        _LOGGER.debug("Calling url: %s...", url)
        result = {SUCCESS: False, MESSAGE: None}
        resp = None
        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10, loop=self.hass.loop):
                resp = yield from websession.get(url)

                result[SUCCESS] = (resp.status == 200)
                result[STATUS_CODE] = resp.status
                result[CONTENT] = yield from resp.text()

                return result
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            result[MESSAGE] = "%s" % err
            return result
        finally:
            if resp is not None:
                yield from resp.release()

    @asyncio.coroutine
    def async_update(self, *_):
        """Update the data from buienradar."""
        from buienradar.buienradar import (parse_data, CONTENT,
                                           DATA, MESSAGE, STATUS_CODE, SUCCESS)

        result = yield from self.get_data('http://xml.buienradar.nl')
        if result.get(SUCCESS, False) is False:
            result = yield from self.get_data('http://api.buienradar.nl')

        if result.get(SUCCESS):
            result = parse_data(result.get(CONTENT),
                                latitude=self.coordinates[CONF_LATITUDE],
                                longitude=self.coordinates[CONF_LONGITUDE])
            if result.get(SUCCESS):
                self.data = result.get(DATA)

                yield from self.update_devices()

                yield from self.schedule_update(10)
            else:
                yield from self.schedule_update(2)
        else:
            # unable to get the data
            _LOGGER.warning("Unable to retrieve data from Buienradar."
                            "(Msg: %s, status: %s,)",
                            result.get(MESSAGE),
                            result.get(STATUS_CODE),)
            # schedule new call
            yield from self.schedule_update(2)

    @property
    def attribution(self):
        """Return the attribution."""
        from buienradar.buienradar import ATTRIBUTION
        return self.data.get(ATTRIBUTION)

    @property
    def stationname(self):
        """Return the name of the selected weatherstation."""
        from buienradar.buienradar import STATIONNAME
        return self.data.get(STATIONNAME)

    @property
    def condition(self):
        """Return the condition."""
        from buienradar.buienradar import SYMBOL
        return self.data.get(SYMBOL)

    @property
    def temperature(self):
        """Return the temperature, or None."""
        from buienradar.buienradar import TEMPERATURE
        try:
            return float(self.data.get(TEMPERATURE))
        except (ValueError, TypeError):
            return None

    @property
    def pressure(self):
        """Return the pressure, or None."""
        from buienradar.buienradar import PRESSURE
        try:
            return float(self.data.get(PRESSURE))
        except (ValueError, TypeError):
            return None

    @property
    def humidity(self):
        """Return the humidity, or None."""
        from buienradar.buienradar import HUMIDITY
        try:
            return int(self.data.get(HUMIDITY))
        except (ValueError, TypeError):
            return None

    @property
    def wind_speed(self):
        """Return the windspeed, or None."""
        from buienradar.buienradar import WINDSPEED
        try:
            return float(self.data.get(WINDSPEED))
        except (ValueError, TypeError):
            return None

    @property
    def wind_bearing(self):
        """Return the wind bearing, or None."""
        from buienradar.buienradar import WINDDIRECTION
        try:
            return int(self.data.get(WINDDIRECTION))
        except (ValueError, TypeError):
            return None

    @property
    def forecast(self):
        """Return the forecast data."""
        from buienradar.buienradar import FORECAST
        return self.data.get(FORECAST)
