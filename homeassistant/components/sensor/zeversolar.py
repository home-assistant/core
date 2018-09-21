"""
Sensor for retrieving the value's of your Zeversolar inverter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zeverzolar/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, STATE_UNKNOWN, CONF_NAME, CONF_RESOURCES)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://www.zevercloud.com/api/v1/getPlantOverview?key='

DEFAULT_NAME = 'ZeverSolar'

DOMAIN = 'zeversolar'
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)

SENSOR_TYPES = {
    'sid': ['sid', 'ID'],
    'E-Today': ['Energy Today', ''],
    'E-Month': ['Energy Month', ''],
    'E-Total': ['Energy Total', ''],
    'TotalYield': ['Total Yield', ''],
    'CO2Avoided': ['CO2 Avoided', ''],
    'Power': ['Power', '']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_RESOURCES, default=['sid']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Zeversolar sensor."""
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    url = (_RESOURCE + api_key)
    var_conf = config.get(CONF_RESOURCES)

    rest = ZeverzolarData(url)
    rest.update()

    sensors = []
    for resource in var_conf:
        sensors.append(ZeverzolarSensor(rest, name, resource))

    add_devices(sensors, True)


class ZeverzolarSensor(Entity):
    """Implementation of a Zeversolar sensor."""

    def __init__(self, rest, name, sensor_type):
        """Initialize the sensor."""
        self.rest = rest
        self._name = name
        self.type = sensor_type
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._name is None:
            return SENSOR_TYPES[self.type][0]
        return '{} {}'.format(self._name, SENSOR_TYPES[self.type][0])

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.rest.data is not None

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    def update(self):
        """Get the latest data from REST API."""
        self.rest.update()
        value = self.rest.data

        if value is not None:
            if self.type == 'sid':
                self._state = value['sid']
            elif self.type == 'E-Today':
                self._state = value['E-Today']['value']
                self._unit_of_measurement = value['E-Today']['unit']
            elif self.type == 'E-Month':
                self._state = value['E-Month']['value']
                self._unit_of_measurement = value['E-Month']['unit']
            elif self.type == 'E-Total':
                self._state = value['E-Total']['value']
                self._unit_of_measurement = value['E-Total']['unit']
            elif self.type == 'TotalYield':
                self._state = value['TotalYield']['value']
                self._unit_of_measurement = value['TotalYield']['unit']
            elif self.type == 'CO2Avoided':
                self._state = value['CO2Avoided']['value']
                self._unit_of_measurement = value['CO2Avoided']['unit']
            elif self.type == 'Power':
                self._state = value['Power']['value']
                self._unit_of_measurement = value['Power']['unit']


class ZeverzolarData:
    """Get data from ZeverSolar."""

    def __init__(self, resource):
        """Initialize the data object."""
        self._resource = resource
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Zeversolar REST API."""
        try:
            response = requests.get(self._resource, timeout=10)
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Connection error: %s", self._resource)
            self.data = None
