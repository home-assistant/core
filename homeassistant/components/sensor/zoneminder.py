"""
Support for ZoneMinder Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zoneminder/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
        STATE_UNKNOWN, CONF_MONITORED_VARIABLES)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.components.zoneminder as zoneminder

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']

SENSOR_TYPES = {
        'events',
        'function',
        'status'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES, default=[]):
        [vol.In(SENSOR_TYPES)],
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ZoneMinder sensor platform."""
    sensors = []

    monitors = zoneminder.get_state('api/monitors.json')
    for i in monitors['monitors']:
        for variable in config[CONF_MONITORED_VARIABLES]:
            sensors.append(ZMSensor(int(i['Monitor']['Id']), i['Monitor']['Name'], variable))

    add_devices(sensors)


class ZMSensor(Entity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor_id, monitor_name, sensor_type):
        """Initiate monitor sensor."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._name = monitor_name + ' ' + sensor_type.capitalize()
        self._type = sensor_type
        self._state = STATE_UNKNOWN

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor state and status."""

        if self._type == "function":
            monitor = zoneminder.get_state(
                'api/monitors/%i.json' % self._monitor_id
            )
            self._state = monitor['monitor']['Monitor']['Function']
        elif self._type == "status":
            monitor = zoneminder.get_state(
                'api/monitors/alarm/id:%i/command:status.json' %
                self._monitor_id
            )
            self._state = int(monitor['status'])
        elif self._type == "events":
            event = zoneminder.get_state(
                    'api/events/index/MonitorId:%i.json' %
                    (self._monitor_id)
            )
            self._state = event['pagination']['count']
