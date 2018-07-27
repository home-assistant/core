"""
Interfaces with SimpliSafe alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.simplisafe/
"""
import logging
import re

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA, AlarmControlPanel)
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['simplisafe-python==2.0.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'SimpliSafe'

ATTR_ALARM_ACTIVE = "alarm_active"
ATTR_TEMPERATURE = "temperature"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SimpliSafe platform."""
    from simplipy.api import SimpliSafeApiInterface, SimpliSafeAPIException
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        simplisafe = SimpliSafeApiInterface(username, password)
    except SimpliSafeAPIException:
        _LOGGER.error("Failed to setup SimpliSafe")
        return

    systems = []

    for system in simplisafe.get_systems():
        systems.append(SimpliSafeAlarm(system, name, code))

    add_devices(systems)


class SimpliSafeAlarm(AlarmControlPanel):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, simplisafe, name, code):
        """Initialize the SimpliSafe alarm."""
        self.simplisafe = simplisafe
        self._name = name
        self._code = str(code) if code else None

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self.simplisafe.location_id

    @property
    def name(self):
        """Return the name of the device."""
        if self._name is not None:
            return self._name
        return 'Alarm {}'.format(self.simplisafe.location_id)

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and re.search('^\\d+$', self._code):
            return 'Number'
        return 'Any'

    @property
    def state(self):
        """Return the state of the device."""
        status = self.simplisafe.state
        if status.lower() == 'off':
            state = STATE_ALARM_DISARMED
        elif status.lower() == 'home' or status.lower() == 'home_count':
            state = STATE_ALARM_ARMED_HOME
        elif (status.lower() == 'away' or status.lower() == 'exitDelay' or
              status.lower() == 'away_count'):
            state = STATE_ALARM_ARMED_AWAY
        else:
            state = STATE_UNKNOWN
        return state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}

        attributes[ATTR_ALARM_ACTIVE] = self.simplisafe.alarm_active
        if self.simplisafe.temperature is not None:
            attributes[ATTR_TEMPERATURE] = self.simplisafe.temperature

        return attributes

    def update(self):
        """Update alarm status."""
        self.simplisafe.update()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return
        self.simplisafe.set_state('off')
        _LOGGER.info("SimpliSafe alarm disarming")

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return
        self.simplisafe.set_state('home')
        _LOGGER.info("SimpliSafe alarm arming home")

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return
        self.simplisafe.set_state('away')
        _LOGGER.info("SimpliSafe alarm arming away")

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check
