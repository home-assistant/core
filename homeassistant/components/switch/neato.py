"""
Support for Neato Connected Vaccums switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.neato/
"""
import time
import logging

from homeassistant.const import (STATE_OFF, STATE_ON, STATE_UNAVAILABLE)
from homeassistant.components.neato import HUB as hub
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPE_CLEAN = 'clean'
SWITCH_TYPE_SCHEDULE = 'scedule'

SWITCH_TYPES = {
    SWITCH_TYPE_CLEAN: ['Clean'],
    SWITCH_TYPE_SCHEDULE: ['Schedule']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Neato switches."""
    if not hub.robots_states:
        return False

    dev = []
    for robot in hub.robots_states:
        for type_name in SWITCH_TYPES:
            dev.append(NeatoConnectedSwitch(robot, type_name))
    _LOGGER.debug('Adding switches %s', dev)
    add_devices(dev)


class NeatoConnectedSwitch(ToggleEntity):
    """Neato Connected Switches."""

    def __init__(self, robot, switch_type):
        """Initialize the Neato Connected switches."""
        self.type = switch_type
        self.robot = robot
        self._robot_name = self.robot.name + ' ' + SWITCH_TYPES[self.type][0]
        self._state = hub.robots_states.get(self.robot)
        self._schedule_state = None
        self._clean_state = None

    def update(self):
        """Update the states of Neato switches."""
        _LOGGER.debug('Running switch update')
        hub.update_robots()
        _LOGGER.debug('self._state=%s', self._state)
        if self.type == SWITCH_TYPE_CLEAN:
            if not self._state:
                self._clean_state = STATE_UNAVAILABLE
                return
            if (not self._state['availableCommands']['start'] and
                    not self._state['availableCommands']['stop'] and
                    not self._state['availableCommands']['pause'] and
                    not self._state['availableCommands']['resume'] and
                    not self._state['availableCommands']['goToBase']):
                self._clean_state = STATE_UNAVAILABLE
                return
            if (self.robot.state['action'] == 1 and
                    self.robot.state['state'] == 2):
                self._clean_state = STATE_ON
            else:
                self._clean_state = STATE_OFF

        if self.type == SWITCH_TYPE_SCHEDULE:
            _LOGGER.debug('self._state=%s', self._state)
            if not self._state:
                self._schedule_state = STATE_UNAVAILABLE
                return
            if self.robot.schedule_enabled:
                self._schedule_state = STATE_ON
            else:
                self._schedule_state = STATE_OFF

    @property
    def state(self):
        """Return the switch state."""
        if self.type == SWITCH_TYPE_CLEAN:
            _LOGGER.debug('clean_state=%s', self._clean_state)
            if self._clean_state is not None:
                return self._clean_state
            else:
                return STATE_UNAVAILABLE
        if self.type == SWITCH_TYPE_SCHEDULE:
            _LOGGER.debug('schedule_state=%s', self._schedule_state)
            if self._schedule_state is not None:
                return self._schedule_state
            else:
                return STATE_UNAVAILABLE

    @property
    def name(self):
        """Return the name of the switch."""
        return self._robot_name

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.type == SWITCH_TYPE_CLEAN:
            if self._clean_state == STATE_ON:
                return True
            return False
        elif self.type == SWITCH_TYPE_SCHEDULE:
            if self._schedule_state is True:
                return True
            return False

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.type == SWITCH_TYPE_CLEAN:
            self.robot.start_cleaning()
        elif self.type == SWITCH_TYPE_SCHEDULE:
            self.robot.enable_schedule()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.type == SWITCH_TYPE_CLEAN:
            self.robot.pause_cleaning()
            time.sleep(1)
            self.robot.send_to_base()
        elif self.type == SWITCH_TYPE_SCHEDULE:
            self.robot.disable_schedule()
