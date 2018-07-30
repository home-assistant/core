"""
Support for ZoneMinder Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zoneminder/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.components import zoneminder
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']

CONF_INCLUDE_ARCHIVED = "include_archived"

DEFAULT_INCLUDE_ARCHIVED = False

SENSOR_TYPES = {
    'all': ['Events'],
    'hour': ['Events Last Hour'],
    'day': ['Events Last Day'],
    'week': ['Events Last Week'],
    'month': ['Events Last Month'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_INCLUDE_ARCHIVED, default=DEFAULT_INCLUDE_ARCHIVED):
        cv.boolean,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['all']):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ZoneMinder sensor platform."""
    include_archived = config.get(CONF_INCLUDE_ARCHIVED)

    sensors = []

    monitors = zoneminder.get_state('api/monitors.json')
    for i in monitors['monitors']:
        sensors.append(
            ZMSensorMonitors(int(i['Monitor']['Id']), i['Monitor']['Name'])
        )

        for sensor in config[CONF_MONITORED_CONDITIONS]:
            sensors.append(
                ZMSensorEvents(int(i['Monitor']['Id']),
                               i['Monitor']['Name'],
                               include_archived, sensor)
            )

    add_devices(sensors)


class ZMSensorMonitors(Entity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor_id, monitor_name):
        """Initialize monitor sensor."""
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
            'api/monitors/{}.json'.format(self._monitor_id)
        )
        if monitor['monitor']['Monitor']['Function'] is None:
            self._state = STATE_UNKNOWN
        else:
            self._state = monitor['monitor']['Monitor']['Function']


class ZMSensorEvents(Entity):
    """Get the number of events for each monitor."""

    def __init__(self, monitor_id, monitor_name, include_archived,
                 sensor_type):
        """Initialize event sensor."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._include_archived = include_archived
        self._type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._monitor_name, self._name)

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
        date_filter = '1%20{}'.format(self._type)
        if self._type == 'all':
            # The consoleEvents API uses DATE_SUB, so give it
            # something large
            date_filter = '100%20year'

        archived_filter = '/Archived=:0'
        if self._include_archived:
            archived_filter = ''

        event = zoneminder.get_state(
            'api/events/consoleEvents/{}{}.json'.format(date_filter,
                                                        archived_filter)
        )

        try:
            self._state = event['results'][str(self._monitor_id)]
        except (TypeError, KeyError):
            self._state = '0'
