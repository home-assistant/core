"""
homeassistant.components.alarm_control_panel.alarmdotcom
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Verisure alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdotcom/
"""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from homeassistant.const import (
    STATE_UNKNOWN,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY)

_LOGGER = logging.getLogger(__name__)


REQUIREMENTS = ['https://github.com/Xorso/pyalarmdotcom'
                '/archive/0.0.7.zip'
                '#pyalarmdotcom==0.0.7']
DEFAULT_NAME = 'Alarm.com'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup an Alarm.com control panel. """

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if username is None or password is None:
        _LOGGER.error('Must specify username and password!')
        return False

    add_devices([AlarmDotCom(hass,
                             config.get('name', DEFAULT_NAME),
                             config.get('code'),
                             username,
                             password)])


# pylint: disable=too-many-arguments, too-many-instance-attributes
# pylint: disable=abstract-method
class AlarmDotCom(alarm.AlarmControlPanel):
    """ Represents a Alarm.com status. """

    def __init__(self, hass, name, code, username, password):
        from pyalarmdotcom.pyalarmdotcom import Alarmdotcom
        self._alarm = Alarmdotcom(username, password, timeout=10)
        self._hass = hass
        self._name = name
        self._code = str(code) if code else None
        self._username = username
        self._password = password

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def code_format(self):
        """ One or more characters if code is defined. """
        return None if self._code is None else '.+'

    @property
    def state(self):
        """ Returns the state of the device. """
        if self._alarm.state == 'Disarmed':
            return STATE_ALARM_DISARMED
        elif self._alarm.state == 'Armed Stay':
            return STATE_ALARM_ARMED_HOME
        elif self._alarm.state == 'Armed Away':
            return STATE_ALARM_ARMED_AWAY
        else:
            return STATE_UNKNOWN

    def alarm_disarm(self, code=None):
        """ Send disarm command. """
        if not self._validate_code(code, 'arming home'):
            return
        from pyalarmdotcom.pyalarmdotcom import Alarmdotcom
        # Open another session to alarm.com to fire off the command
        _alarm = Alarmdotcom(self._username, self._password, timeout=10)
        _alarm.disarm()
        self.update_ha_state()

    def alarm_arm_home(self, code=None):
        """ Send arm home command. """
        if not self._validate_code(code, 'arming home'):
            return
        from pyalarmdotcom.pyalarmdotcom import Alarmdotcom
        # Open another session to alarm.com to fire off the command
        _alarm = Alarmdotcom(self._username, self._password, timeout=10)
        _alarm.arm_stay()
        self.update_ha_state()

    def alarm_arm_away(self, code=None):
        """ Send arm away command. """
        if not self._validate_code(code, 'arming home'):
            return
        from pyalarmdotcom.pyalarmdotcom import Alarmdotcom
        # Open another session to alarm.com to fire off the command
        _alarm = Alarmdotcom(self._username, self._password, timeout=10)
        _alarm.arm_away()
        self.update_ha_state()

    def _validate_code(self, code, state):
        """ Validate given code. """
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning('Wrong code entered for %s', state)
        return check
