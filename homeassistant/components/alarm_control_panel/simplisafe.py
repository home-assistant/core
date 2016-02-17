"""
homeassistant.components.alarm_control_panel.simplisafe
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with SimpliSafe alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/simplisafe/
"""
import logging

import homeassistant.components.alarm_control_panel as alarm

from homeassistant.const import (
    STATE_UNKNOWN,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the SimpliSafe platform. """

    add_devices([SimpliSafeAlarm(
        config.get('name', "SimpliSafe"),
        config.get('username'),
        config.get('password')
        )])


# pylint: disable=abstract-method
class SimpliSafeAlarm(alarm.AlarmControlPanel):
    """ Represents a SimpliSafeAlarm alarm status. """

    def __init__(self, name, username, password):
        from simplisafe import SimpliSafe
        self.simplisafe = SimpliSafe() 
        self._username = username
        self._password = password
        self._name = name
        self.simplisafe.login(self._username, self._password)
        self._id = self.simplisafe.get_id()
        self._state = self.simplisafe.get_state()
        self.simplisafe.logout()

    @property
    def name(self):
        """ Returns the name of the device. """
        if self._name is not None:
            return self._name
        else:
            return 'Alarm {}'.format(self._id)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    def update(self):
        """ Update alarm status """
        self.simplisafe.login(self._username, self._password)
        status = self.simplisafe.get_state()
        self.simplisafe.logout()

        if status == 'Off':
            self._state = STATE_ALARM_DISARMED
        elif status == 'Home':
            self._state = STATE_ALARM_ARMED_HOME
        elif status == 'Away':
            self._state = STATE_ALARM_ARMED_AWAY

    def alarm_disarm(self, code=None):
        """ Send disarm command. """
        self.simplisafe.login(self._username, self._password)
        self.simplisafe.set_state('off')
        self.simplisafe.logout()
        _LOGGER.info('SimpliSafe alarm disarming')
        self.update()

    def alarm_arm_home(self, code=None):
        """ Send arm home command. """
        self.simplisafe.login(self._username, self._password)
        self.simplisafe.set_state('home')
        self.simplisafe.logout()
        _LOGGER.info('SimpliSafe alarm arming home')
        self.update()

    def alarm_arm_away(self, code=None):
        """ Send arm away command. """
        self.simplisafe.login(self._username, self._password)
        self.simplisafe.set_state('away')
        self.simplisafe.logout()
        _LOGGER.info('SimpliSafe alarm arming away')
        self.update()
