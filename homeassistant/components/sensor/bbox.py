"""
Support for Bbox Bouygues Modem Router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bbox/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_MONITORED_VARIABLES, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pybbox==0.0.5-alpha']

_LOGGER = logging.getLogger(__name__)

BANDWIDTH_MEGABITS_SECONDS = 'Mb/s'  # type: str

ATTRIBUTION = "Powered by Bouygues Telecom"

DEFAULT_NAME = 'Bbox'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# Sensor types are defined like so: Name, unit, icon
SENSOR_TYPES = {
    'down_max_bandwidth': ['Maximum Download Bandwidth',
                           BANDWIDTH_MEGABITS_SECONDS, 'mdi:download'],
    'up_max_bandwidth': ['Maximum Upload Bandwidth',
                         BANDWIDTH_MEGABITS_SECONDS, 'mdi:upload'],
    'current_down_bandwidth': ['Currently Used Download Bandwidth',
                               BANDWIDTH_MEGABITS_SECONDS, 'mdi:download'],
    'current_up_bandwidth': ['Currently Used Upload Bandwidth',
                             BANDWIDTH_MEGABITS_SECONDS, 'mdi:upload'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Bbox sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.
    try:
        bbox_data = BboxData()
        bbox_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(BboxSensor(bbox_data, variable, name))

    add_devices(sensors, True)


class BboxSensor(Entity):
    """Implementation of a Bbox sensor."""

    def __init__(self, bbox_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.bbox_data = bbox_data
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def update(self):
        """Get the latest data from Bbox and update the state."""
        self.bbox_data.update()
        if self.type == 'down_max_bandwidth':
            self._state = round(
                self.bbox_data.data['rx']['maxBandwidth'] / 1000, 2)
        elif self.type == 'up_max_bandwidth':
            self._state = round(
                self.bbox_data.data['tx']['maxBandwidth'] / 1000, 2)
        elif self.type == 'current_down_bandwidth':
            self._state = round(self.bbox_data.data['rx']['bandwidth'] / 1000,
                                2)
        elif self.type == 'current_up_bandwidth':
            self._state = round(self.bbox_data.data['tx']['bandwidth'] / 1000,
                                2)


class BboxData:
    """Get data from the Bbox."""

    def __init__(self):
        """Initialize the data object."""
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Bbox."""
        import pybbox

        try:
            box = pybbox.Bbox()
            self.data = box.get_ip_stats()
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(error)
            self.data = None
            return False
