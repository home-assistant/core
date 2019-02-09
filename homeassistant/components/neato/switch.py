"""
Support for Neato Connected Vacuums switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.neato/
"""
import logging
from datetime import timedelta
import requests
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.neato import NEATO_ROBOTS, NEATO_LOGIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['neato']

SCAN_INTERVAL = timedelta(minutes=10)

SWITCH_TYPE_SCHEDULE = 'schedule'

SWITCH_TYPES = {
    SWITCH_TYPE_SCHEDULE: ['Schedule']
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Neato switches."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        for type_name in SWITCH_TYPES:
            dev.append(NeatoConnectedSwitch(hass, robot, type_name))
    _LOGGER.debug("Adding switches %s", dev)
    add_entities(dev)


class NeatoConnectedSwitch(ToggleEntity):
    """Neato Connected Switches."""

    def __init__(self, hass, robot, switch_type):
        """Initialize the Neato Connected switches."""
        self.type = switch_type
        self.robot = robot
        self.neato = hass.data[NEATO_LOGIN]
        self._robot_name = '{} {}'.format(
            self.robot.name, SWITCH_TYPES[self.type][0])
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            _LOGGER.warning("Neato connection error: %s", ex)
            self._state = None
        self._schedule_state = None
        self._clean_state = None
        self._robot_serial = self.robot.serial

    def update(self):
        """Update the states of Neato switches."""
        _LOGGER.debug("Running switch update")
        self.neato.update_robots()
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            _LOGGER.warning("Neato connection error: %s", ex)
            self._state = None
            return
        _LOGGER.debug('self._state=%s', self._state)
        if self.type == SWITCH_TYPE_SCHEDULE:
            _LOGGER.debug("State: %s", self._state)
            if self._state['details']['isScheduleEnabled']:
                self._schedule_state = STATE_ON
            else:
                self._schedule_state = STATE_OFF
            _LOGGER.debug("Schedule state: %s", self._schedule_state)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._robot_name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._robot_serial

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            if self._schedule_state == STATE_ON:
                return True
            return False

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            self.robot.enable_schedule()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.type == SWITCH_TYPE_SCHEDULE:
            self.robot.disable_schedule()
