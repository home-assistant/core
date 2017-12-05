"""
Support for Luftdaten sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.luftdaten/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['luftdaten==0.1.1']

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_ID = 'sensor_id'

CONF_ATTRIBUTION = "Data provided by luftdaten.info"


VOLUME_MICROGRAMS_PER_CUBIC_METER = 'µg/m3'

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_PM10 = 'P1'
SENSOR_PM2_5 = 'P2'
SENSOR_PRESSURE = 'pressure'

SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ['Temperature', TEMP_CELSIUS],
    SENSOR_HUMIDITY: ['Humidity', '%'],
    SENSOR_PRESSURE: ['Pressure', 'Pa'],
    SENSOR_PM10: ['PM10', VOLUME_MICROGRAMS_PER_CUBIC_METER],
    SENSOR_PM2_5: ['PM2.5', VOLUME_MICROGRAMS_PER_CUBIC_METER]
}

DEFAULT_NAME = 'Luftdaten'

CONF_SENSORID = 'sensorid'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORID): cv.positive_int,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Luftdaten sensor."""
    name = config.get(CONF_NAME)
    sensor_id = config.get(CONF_SENSORID)

    data = LuftdatenData(hass, sensor_id)

    yield from data.async_get()

    devices = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        if data.luftdaten.values[variable] is None:
            _LOGGER.warning("It might be that sensor %s is not providing "
                            "measurements for %s", sensor_id, variable)
        devices.append(LuftdatenSensor(data, name, variable, sensor_id))

    async_add_devices(devices)


class LuftdatenSensor(Entity):
    """Implementation of a Luftdaten sensor."""

    def __init__(self, data, name, sensor_type, sensor_id):
        """Initialize the Luftdaten sensor."""
        self.data = data
        self._name = name
        self._state = None
        self._sensor_id = sensor_id
        self.sensor_type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self.sensor_type][0])

    @property
    def state(self):
        """Return the state of the device."""
        return self.data.luftdaten.values[self.sensor_type]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.data is None:
            return

        attr = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_SENSOR_ID: self._sensor_id,
            'lat': self.data.luftdaten.meta['latitude'],
            'long': self.data.luftdaten.meta['longitude'],
        }
        return attr

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from luftdaten.info and update the state."""
        try:
            yield from self.data.async_get()
        except TypeError:
            pass


class LuftdatenData(object):
    """Class for handling the data retrieval."""

    def __init__(self, hass, sensor_id):
        """Initialize the data object."""
        from luftdaten import Luftdaten

        self.hass = hass
        self._websession = async_get_clientsession(self.hass)
        self.luftdaten = Luftdaten(
            sensor_id, self.hass.loop, self._websession)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    @asyncio.coroutine
    def async_get(self):
        """Get the latest data from luftdaten.info."""
        from luftdaten.exceptions import LuftdatenError

        try:
            yield from self.luftdaten.async_get_data()
        except LuftdatenError:
            _LOGGER.error("Unable to retrieve data from luftdaten.info")
            self.luftdaten = None
