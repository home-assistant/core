"""
Support for state (idle, alarm) of ZoneMinder monitors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.zoneminder/
"""
import logging
from homeassistant.components.binary_sensor import (BinarySensorDevice)
import homeassistant.components.zoneminder as zoneminder

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']
ZM_IDLE = '0'
ZM_TAPE = '4'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZoneMinder sensors."""
    sensors = []

    _LOGGER.debug("Getting monitors")
    monitors = zoneminder.get_state('api/monitors.json')
    for i in monitors['monitors']:
        sensors.append(
            ZMBinarySensor(int(i['Monitor']['Id']), i['Monitor']['Name'])
        )

    _LOGGER.debug("Adding devices")
    add_devices(sensors)


class ZMBinarySensor(BinarySensorDevice):
    """Get the state of each ZoneMinder monitor."""

    def __init__(self, monitor_id, monitor_name):
        """Initiate monitor sensor."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._sensor_class = 'motion'
        self._state = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} Status'.format(self._monitor_name)

    @property
    def is_on(self):
        """Return the status of the sensor."""
        _LOGGER.debug('is on?')
        return self._state

    def update(self):
        """Return the current status of the monitor."""
        _LOGGER.debug("getting status")
        monitor = zoneminder.get_state(
            'api/monitors/alarm/id:%i/command:status.json' % self._monitor_id
        )
        _LOGGER.debug("got status")
        if monitor['status'] == ZM_IDLE:
            self._state = False
        elif monitor['status'] == ZM_TAPE:
            self._state = False
        else:
            self._state = 'Alarm'
