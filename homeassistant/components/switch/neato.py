"""
Support for Neato Connected Vaccums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.neato/
"""
import time
import logging
from datetime import timedelta
from urllib.error import HTTPError
from requests.exceptions import HTTPError as req_HTTPError

import voluptuous as vol

from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME, STATE_OFF,
                                 STATE_ON, STATE_UNAVAILABLE)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/jabesq/pybotvac/archive/v0.0.1.zip'
                '#pybotvac==0.0.1']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

MIN_TIME_TO_WAIT = timedelta(seconds=10)
MIN_TIME_TO_LOCK_UPDATE = 10

SWITCH_TYPES = {
    'clean': ['Clean']
}

DOMAIN = 'neato'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Neato platform."""
    from pybotvac import Account

    try:
        auth = Account(config[CONF_USERNAME], config[CONF_PASSWORD])
    except HTTPError:
        _LOGGER.error("Unable to connect to Neato API")
        return False

    dev = []
    for robot in auth.robots:
        for type_name in SWITCH_TYPES:
            dev.append(NeatoConnectedSwitch(robot, type_name))
    add_devices(dev)


class NeatoConnectedSwitch(ToggleEntity):
    """Neato Connected Switch (clean)."""

    def __init__(self, robot, switch_type):
        """Initialize the Neato Connected switch."""
        self.type = switch_type
        self.robot = robot
        self.lock = False
        self.last_lock_time = None
        self.graceful_state = False
        self._state = None

    def lock_update(self):
        """Lock the update since Neato clean takes some time to start."""
        if self.is_update_locked():
            return
        self.lock = True
        self.last_lock_time = time.time()

    def reset_update_lock(self):
        """Reset the update lock."""
        self.lock = False
        self.last_lock_time = None

    def set_graceful_lock(self, state):
        """Set the graceful state."""
        self.graceful_state = state
        self.reset_update_lock()
        self.lock_update()

    def is_update_locked(self):
        """Check if the update method is locked."""
        if self.last_lock_time is None:
            return False

        if time.time() - self.last_lock_time >= MIN_TIME_TO_LOCK_UPDATE:
            self.last_lock_time = None
            return False

        return True

    @property
    def state(self):
        """Return the state."""
        if not self._state:
            return STATE_UNAVAILABLE
        if not self._state['availableCommands']['start'] and \
           not self._state['availableCommands']['stop'] and \
           not self._state['availableCommands']['pause'] and \
           not self._state['availableCommands']['resume'] and \
           not self._state['availableCommands']['goToBase']:
            return STATE_UNAVAILABLE
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.robot.name + ' ' + SWITCH_TYPES[self.type][0]

    @property
    def is_on(self):
        """Return true if device is on."""
        if self.is_update_locked():
            return self.graceful_state
        if self._state['action'] == 1 and self._state['state'] == 2:
            return True
        return False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.set_graceful_lock(True)
        self.robot.start_cleaning()

    def turn_off(self, **kwargs):
        """Turn the device off (Return Robot to base)."""
        self.robot.pause_cleaning()
        time.sleep(1)
        self.robot.send_to_base()

    def update(self):
        """Refresh Robot state from Neato API."""
        try:
            self._state = self.robot.state
        except req_HTTPError:
            _LOGGER.error("Unable to retrieve to Robot State.")
            self._state = None
            return False
