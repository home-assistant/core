"""
Support for Luftdaten sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.luftdaten/
"""
import asyncio
import json
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE, CONF_VERIFY_SSL, CONF_MONITORED_CONDITIONS,
    TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

VOLUME_MICROGRAMS_PER_CUBIC_METER = 'µg/m3'

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_PM10 = 'P1'
SENSOR_PM2_5 = 'P2'

SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ['Temperature', TEMP_CELSIUS],
    SENSOR_HUMIDITY: ['Humidity', '%'],
    SENSOR_PM10: ['PM10', VOLUME_MICROGRAMS_PER_CUBIC_METER],
    SENSOR_PM2_5: ['PM2.5', VOLUME_MICROGRAMS_PER_CUBIC_METER]
}

DEFAULT_NAME = 'Luftdaten Sensor'
DEFAULT_RESOURCE = 'https://api.luftdaten.info/v1/sensor/'
DEFAULT_VERIFY_SSL = True

CONF_SENSORID = 'sensorid'

SCAN_INTERVAL = timedelta(minutes=3)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORID): cv.positive_int,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_RESOURCE, default=DEFAULT_RESOURCE): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Luftdaten sensor."""
    name = config.get(CONF_NAME)
    sensorid = config.get(CONF_SENSORID)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    resource = '{}{}/'.format(config.get(CONF_RESOURCE), sensorid)

    rest_client = LuftdatenData(resource, verify_ssl)
    rest_client.update()

    if rest_client.data is None:
        _LOGGER.error("Unable to fetch Luftdaten data")
        return False

    devices = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        devices.append(LuftdatenSensor(rest_client, name, variable))

    async_add_devices(devices, True)


class LuftdatenSensor(Entity):
    """Implementation of a LuftdatenSensor sensor."""

    def __init__(self, rest_client, name, sensor_type):
        """Initialize the LuftdatenSensor sensor."""
        self.rest_client = rest_client
        self._name = name
        self._state = None
        self.sensor_type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self.sensor_type][0])

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from REST API and update the state."""
        self.rest_client.update()
        value = self.rest_client.data

        if value is None:
            self._state = None
        else:
            parsed_json = json.loads(value)

            log_entries_count = len(parsed_json) - 1
            latest_log_entry = parsed_json[log_entries_count]
            sensordata_values = latest_log_entry['sensordatavalues']
            for sensordata_value in sensordata_values:
                if sensordata_value['value_type'] == self.sensor_type:
                    self._state = sensordata_value['value']


class LuftdatenData(object):
    """Class for handling the data retrieval."""

    def __init__(self, resource, verify_ssl):
        """Initialize the data object."""
        self._request = requests.Request('GET', resource).prepare()
        self._verify_ssl = verify_ssl
        self.data = None

    def update(self):
        """Get the latest data from Luftdaten service."""
        try:
            with requests.Session() as sess:
                response = sess.send(
                    self._request, timeout=10, verify=self._verify_ssl)

            self.data = response.text
        except requests.exceptions.RequestException:
            _LOGGER.error("Error fetching data: %s", self._request)
            self.data = None
