"""
Support for Neato Connected Vaccums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/vacuum.neato/
"""
import logging
import requests
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.components.vacuum import (SUPPORT_BATTERY,
                                             SUPPORT_PAUSE,
                                             SUPPORT_RETURN_HOME,
                                             SUPPORT_STATUS, SUPPORT_STOP,
                                             SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
                                             SUPPORT_MAP, ATTR_STATUS,
                                             ATTR_BATTERY_LEVEL,
                                             ATTR_BATTERY_ICON, VacuumDevice)
from homeassistant.components.neato import (
    NEATO_ROBOTS, NEATO_LOGIN, ACTION, ERRORS, MODE, ALERTS)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['neato']

SUPPORT_NEATO = SUPPORT_BATTERY | SUPPORT_PAUSE | SUPPORT_RETURN_HOME | \
                 SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
                 SUPPORT_STATUS | SUPPORT_MAP

ICON = "mdi:roomba"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Neato switches."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoConnectedVacuum(hass, robot))
    _LOGGER.debug("Adding vacuums %s", dev)
    add_devices(dev)


class NeatoConnectedVacuum(VacuumDevice):
    """Neato Connected Vacuums."""

    def __init__(self, hass, robot):
        """Initialize the Neato Connected Vacuums."""
        self.robot = robot
        self.neato = hass.data[NEATO_LOGIN]
        self._name = '{}'.format(self.robot.name)
        self._status_state = None
        self._clean_state = None
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            _LOGGER.warning("Neato connection error: %s", ex)
            self._state = None

    def update(self):
        """Update the states of Neato Vacuums."""
        _LOGGER.debug("Running Vacuums update")
        self.neato.update_robots()
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            _LOGGER.warning("Neato connection error: %s", ex)
            self._state = None
            return
        _LOGGER.debug('self._state=%s', self._state)
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
                self._status_state = (
                    MODE.get(self._state['cleaning']['mode'])
                    + ' ' + ACTION.get(self._state['action']))
            else:
                self._status_state = ALERTS.get(self._state['error'])
        elif self._state['state'] == 3:
            self._status_state = 'Paused'
        elif self._state['state'] == 4:
            self._status_state = ERRORS.get(self._state['error'])

        if (self.robot.state['action'] == 1 or
            self.robot.state['action'] == 2 or
            self.robot.state['action'] == 3 and
            self.robot.state['state'] == 2):
            self._clean_state = STATE_ON
        else:
            self._clean_state = STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device."""
        return ICON

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_NEATO

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._state['details']['charge']

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self._status_state

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self.status is not None:
            data[ATTR_STATUS] = self.status

        if self.battery_level is not None:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        return data

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        self.robot.start_cleaning()

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self._clean_state == STATE_ON:
            return True
        return False

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.robot.pause_cleaning()
        self.robot.send_to_base()

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        self.robot.send_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        self.robot.stop_cleaning()

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self._state['state'] == 1:
            self.robot.start_cleaning()
        elif self._state['state'] == 2:
            if ALERTS.get(self._state['error']) is None:
                self.robot.pause_cleaning()
        if self._state['state'] == 3:
            self.robot.resume_cleaning()
