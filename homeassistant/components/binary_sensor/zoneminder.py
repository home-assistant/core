"""
Support for state (idle, alarm) of ZoneMinder monitors

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.zoneminder/
"""
import logging
from homeassistant.components.binary_sensor import BinarySensorDevice
import homeassistant.components.zoneminder as zoneminder
from homeassistant.helpers.event import track_time_change

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']

CONF_SECOND = 'second'

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZoneMinder sensors."""
    sensors = []

    _LOGGER.debug("Getting monitors")
    monitors = zoneminder.get_state('api/monitors.json')
    for i in monitors['monitors']:
        sensors.append(
            ZMBinarySensor(hass, config, int(i['Monitor']['Id']), i['Monitor']['Name'])
        )

    _LOGGER.debug("Adding devices")
    add_devices(sensors)

class ZMBinarySensor(BinarySensorDevice):
    """Get the state of each ZoneMinder monitor."""

    def __init__(self, hass, config, monitor_id, monitor_name):
        """Initiate monitor sensor."""
        self._monitor_id = monitor_id
        self._monitor_name = monitor_name
        self._sensor_class = 'motion'
        self._state = False
        track_time_change(hass, self.update, second=config.get(CONF_SECOND))

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} Status'.format(self._monitor_name)

    @property
    def is_on(self):
        """Return the status of the sensor."""
        _LOGGER.debug('is on?')
        return self._state

    def update(self, now):
        """Return the current status of the monitor."""
        _LOGGER.debug("getting status")
        monitor = zoneminder.get_state(
            'api/monitors/alarm/id:%i/command:status.json' % self._monitor_id
        )
        """Refer to the output of `zmu -h` for what these status codes mean"""
        _LOGGER.debug("got status")
        if monitor['status'] == '0':
            self._state = False
        elif monitor['status'] == '4':
            self._state = False
        else:
            self._state = 'Alarm'
