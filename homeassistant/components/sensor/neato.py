"""
Support for Neato Connected Vaccums sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.neato/
"""
import logging

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.components.neato import HUB as hub
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPE_STATUS = 'status'
SENSOR_TYPE_BATTERY = 'battery'

SENSOR_TYPES = {
    SENSOR_TYPE_STATUS: ['Status'],
    SENSOR_TYPE_BATTERY: ['Battery']
}

STATES = {
    1: 'Idle',
    2: 'Busy',
    3: 'Pause',
    4: 'Error'
}

MODE = {
    1: 'Eco',
    2: 'Turbo'
}

ACTION = {
    0: 'No action',
    1: 'House cleaning',
    2: 'Spot cleaning',
    3: 'Manual cleaning',
    4: 'Docking',
    5: 'User menu active',
    6: 'Cleaning cancelled',
    7: 'Updating...',
    8: 'Copying logs...',
    9: 'Calculating position...',
    10: 'IEC test'
}

ERRORS = {
    'ui_error_brush_stuck': 'Brush stuck',
    'ui_error_brush_overloaded': 'Brush overloaded',
    'ui_error_bumper_stuck': 'Bumper stuck',
    'ui_error_dust_bin_missing': 'Dust bin missing',
    'ui_error_dust_bin_full': 'Dust bin full',
    'ui_error_dust_bin_emptied': 'Dust bin emptied',
    'ui_error_navigation_noprogress': 'Clear my path',
    'ui_error_navigation_origin_unclean': 'Clear my path',
    'ui_error_navigation_falling': 'Clear my path',
    'ui_error_picked_up': 'Picked up',
    'ui_error_stuck': 'Stuck!'

}

ALERTS = {
    'ui_alert_dust_bin_full': 'Please empty dust bin',
    'ui_alert_recovering_location': 'Returning to start'
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Neato sensor platform."""
    if not hub.robots_states:
        return False

    dev = []
    for robot in hub.robots_states:
        for type_name in SENSOR_TYPES:
            dev.append(NeatoConnectedSensor(robot, type_name))
    _LOGGER.debug('Adding sensors %s', dev)
    add_devices(dev)


class NeatoConnectedSensor(Entity):
    """Neato Connected Sensor."""

    def __init__(self, robot, sensor_type):
        """Initialize the Neato Connected sensor."""
        self.type = sensor_type
        self.robot = robot
        self._robot_name = self.robot.name + ' ' + SENSOR_TYPES[self.type][0]
        self._state = hub.robots_states.get(self.robot)
        self._battery_state = None
        self._status_state = None

    def update(self):
        """Update the properties of sensor."""
        _LOGGER.debug('Update of sensor')
        hub.update_robots()
        self._state = hub.robots_states.get(self.robot)
        _LOGGER.debug('self._state=%s', self._state)
        if self.type == SENSOR_TYPE_STATUS:
            if self._state is None:
                self._status_state = STATE_UNAVAILABLE
            if self._state['state'] == 1:
                if self._state['details']['isCharging']:
                    self._status_state = 'Charging'
                elif (self._state['details']['isDocked'] and
                      not self._state['details']['isCharging']):
                    self._status_state = 'Docked'
                else:
                    self._status_state = 'Stopped'
            elif self._state['state'] == 2:
                if ALERTS.get(self._state['error']) is None:
                    self._status_state = (MODE.get(
                        self._state['cleaning']['mode']) + ' ' +
                                          ACTION.get(self._state['action']))
                else:
                    self._status_state = ALERTS.get(self._state['error'])
            elif self._state['state'] == 3:
                self._status_state = 'Paused'
            elif self._state['state'] == 4:
                self._status_state = ERRORS.get(self._state['error'])
        if self.type == SENSOR_TYPE_BATTERY:
            if self._state is None:
                self._battery_state = STATE_UNAVAILABLE
            self._battery_state = self._state['details']['charge']

    @property
    def unit_of_measurement(self):
        """Return unit for the sensor."""
        if self.type == SENSOR_TYPE_BATTERY:
            return '%'

    @property
    def state(self):
        """Return the sensor state."""
        if self.type == SENSOR_TYPE_STATUS:
            _LOGGER.debug('Status state %s', self._status_state)
            if self._status_state is not None:
                return self._status_state
            else:
                return STATE_UNAVAILABLE
        if self.type == SENSOR_TYPE_BATTERY:
            _LOGGER.debug('Battery state %s', self._battery_state)
            if self._battery_state is not None:
                return self._battery_state
            else:
                return STATE_UNAVAILABLE

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._robot_name
