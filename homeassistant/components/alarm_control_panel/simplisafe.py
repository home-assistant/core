"""
Interfaces with SimpliSafe alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.simplisafe/
"""
import logging

import homeassistant.components.alarm_control_panel as alarm

from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['https://github.com/w1ll1am23/simplisafe-python/archive/'
                '586fede0e85fd69e56e516aaa8e97eb644ca8866.zip#'
                'simplisafe-python==0.0.1']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SimpliSafe platform."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if username is None or password is None:
        _LOGGER.error('Must specify username and password!')
        return False

    add_devices([SimpliSafeAlarm(
        config.get('name', "SimpliSafe"),
        username,
        password,
        config.get('code'))])


# pylint: disable=abstract-method
class SimpliSafeAlarm(alarm.AlarmControlPanel):
    """Representation a SimpliSafe alarm."""

    def __init__(self, name, username, password, code):
        """Initialize the SimpliSafe alarm."""
        from simplisafe import SimpliSafe
        self.simplisafe = SimpliSafe(username, password)
        self._name = name
        self._code = str(code) if code else None
        self._id = self.simplisafe.get_id()
        status = self.simplisafe.get_state()
        if status == 'Off':
            self._state = STATE_ALARM_DISARMED
        elif status == 'Home':
            self._state = STATE_ALARM_ARMED_HOME
        elif status == 'Away':
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = STATE_UNKNOWN

    @property
    def should_poll(self):
        """Poll the SimpliSafe API."""
        return True

    @property
    def name(self):
        """Return the name of the device."""
        if self._name is not None:
            return self._name
        else:
            return 'Alarm {}'.format(self._id)

    @property
    def code_format(self):
        """One or more characters if code is defined."""
        return None if self._code is None else '.+'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Update alarm status."""
        self.simplisafe.get_location()
        status = self.simplisafe.get_state()

        if status == 'Off':
            self._state = STATE_ALARM_DISARMED
        elif status == 'Home':
            self._state = STATE_ALARM_ARMED_HOME
        elif status == 'Away':
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = STATE_UNKNOWN

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, 'disarming'):
            return
        self.simplisafe.set_state('off')
        _LOGGER.info('SimpliSafe alarm disarming')
        self.update()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, 'arming home'):
            return
        self.simplisafe.set_state('home')
        _LOGGER.info('SimpliSafe alarm arming home')
        self.update()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, 'arming away'):
            return
        self.simplisafe.set_state('away')
        _LOGGER.info('SimpliSafe alarm arming away')
        self.update()

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning('Wrong code entered for %s', state)
        return check
