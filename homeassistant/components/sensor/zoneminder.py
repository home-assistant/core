"""
Support for ZoneMinder Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zoneminder/
"""
import logging

from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
import homeassistant.components.zoneminder as zoneminder

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ZoneMinder sensor platform."""
    sensors = []

    monitors = zoneminder.get_state('api/monitors.json')
    for i in monitors['monitors']:
        sensors.append(
            ZMSensorMonitors(int(i['Monitor']['Id']), i['Monitor']['Name'])
        )
        sensors.append(
            ZMSensorEvents(int(i['Monitor']['Id']), i['Monitor']['Name'])
        )

    add_devices(sensors)


class ZMSensorMonitors(Entity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor_id, monitor_name):
        """Initiate monitor sensor."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} Status'.format(self._monitor_name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        monitor = zoneminder.get_state(
            'api/monitors/%i.json' % self._monitor_id
        )
        if monitor['monitor']['Monitor']['Function'] is None:
            self._state = STATE_UNKNOWN
        else:
            self._state = monitor['monitor']['Monitor']['Function']


class ZMSensorEvents(Entity):
    """Get the number of events for each monitor."""

    def __init__(self, monitor_id, monitor_name):
        """Initiate event sensor."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} Events'.format(self._monitor_name)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'Events'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        event = zoneminder.get_state(
            'api/events/index/MonitorId:%i.json' % self._monitor_id
        )

        self._state = event['pagination']['count']
