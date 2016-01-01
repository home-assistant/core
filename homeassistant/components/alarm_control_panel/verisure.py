"""
homeassistant.components.alarm_control_panel.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Verisure alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/verisure/
"""
import logging

import homeassistant.components.verisure as verisure
import homeassistant.components.alarm_control_panel as alarm

from homeassistant.const import (
    STATE_UNKNOWN,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Verisure platform. """

    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

    alarms = []

    alarms.extend([
        VerisureAlarm(value)
        for value in verisure.ALARM_STATUS.values()
        if verisure.SHOW_ALARM
        ])

    add_devices(alarms)


# pylint: disable=abstract-method
class VerisureAlarm(alarm.AlarmControlPanel):
    """ Represents a Verisure alarm status. """

    def __init__(self, alarm_status):
        self._id = alarm_status.id
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """ Returns the name of the device. """
        return 'Alarm {}'.format(self._id)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def code_format(self):
        """ Four digit code required. """
        return '^\\d{4}$'

    def update(self):
        """ Update alarm status """
        verisure.update_alarm()

        if verisure.ALARM_STATUS[self._id].status == 'unarmed':
            self._state = STATE_ALARM_DISARMED
        elif verisure.ALARM_STATUS[self._id].status == 'armedhome':
            self._state = STATE_ALARM_ARMED_HOME
        elif verisure.ALARM_STATUS[self._id].status == 'armedaway':
            self._state = STATE_ALARM_ARMED_AWAY
        elif verisure.ALARM_STATUS[self._id].status != 'pending':
            _LOGGER.error(
                'Unknown alarm state %s',
                verisure.ALARM_STATUS[self._id].status)

    def alarm_disarm(self, code=None):
        """ Send disarm command. """
        verisure.MY_PAGES.alarm.set(code, 'DISARMED')
        _LOGGER.info('verisure alarm disarming')
        verisure.MY_PAGES.alarm.wait_while_pending()
        verisure.update_alarm()

    def alarm_arm_home(self, code=None):
        """ Send arm home command. """
        verisure.MY_PAGES.alarm.set(code, 'ARMED_HOME')
        _LOGGER.info('verisure alarm arming home')
        verisure.MY_PAGES.alarm.wait_while_pending()
        verisure.update_alarm()

    def alarm_arm_away(self, code=None):
        """ Send arm away command. """
        verisure.MY_PAGES.alarm.set(code, 'ARMED_AWAY')
        _LOGGER.info('verisure alarm arming away')
        verisure.MY_PAGES.alarm.wait_while_pending()
        verisure.update_alarm()
