"""
homeassistant.components.alarm.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Verisure alarm.
"""
import logging

import homeassistant.components.verisure as verisure
import homeassistant.components.alarm as alarm

from homeassistant.helpers.entity import Entity
<<<<<<< HEAD
from homeassistant.const import (STATE_UNKNOWN,
        STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY)
=======
from homeassistant.const import STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY
>>>>>>> 614caa33ae4b9fd13bd26436dd4c1dd09ff01119

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Verisure platform. """

    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

<<<<<<< HEAD
    alarms = []

    alarms.extend([
=======
    sensors = []

    sensors.extend([
>>>>>>> 614caa33ae4b9fd13bd26436dd4c1dd09ff01119
        VerisureAlarm(value)
        for value in verisure.get_alarm_status().values()
        if verisure.SHOW_ALARM
        ])

<<<<<<< HEAD
    add_devices(alarms)


class VerisureAlarm(alarm.AlarmControl):
=======
    add_devices(sensors)


class VerisureAlarm(Entity):
>>>>>>> 614caa33ae4b9fd13bd26436dd4c1dd09ff01119
    """ represents a Verisure alarm status within home assistant. """

    def __init__(self, alarm_status):
        self._id = alarm_status.id
        self._device = verisure.MY_PAGES.DEVICE_ALARM
<<<<<<< HEAD
        self._state = STATE_UNKNOWN
=======
>>>>>>> 614caa33ae4b9fd13bd26436dd4c1dd09ff01119

    @property
    def name(self):
        """ Returns the name of the device. """
        return 'Alarm {}'.format(self._id)

    @property
    def state(self):
        """ Returns the state of the device. """
        if verisure.STATUS[self._device][self._id].status == 'unarmed':
<<<<<<< HEAD
            self._state = STATE_ALARM_DISARMED
        elif verisure.STATUS[self._device][self._id].status == 'armedhome':
            self._state = STATE_ALARM_ARMED_HOME
        elif verisure.STATUS[self._device][self._id].status == 'armedaway':
            self._state = STATE_ALARM_ARMED_AWAY
        elif verisure.STATUS[self._device][self._id].status != 'pending':
            _LOGGER.error('Unknown alarm state ' +  verisure.STATUS[self._device][self._id].status)
        return self._state
=======
            return STATE_ALARM_DISARMED
        if verisure.STATUS[self._device][self._id].status == 'armed_home':
            return STATE_ALARM_ARMED_HOME
        if verisure.STATUS[self._device][self._id].status == 'armed_away':
            return STATE_ALARM_ARMED_AWAY
>>>>>>> 614caa33ae4b9fd13bd26436dd4c1dd09ff01119

    def update(self):
        ''' update alarm status '''
        verisure.update()
<<<<<<< HEAD
    
    def alarm_disarm(self, code):
        """ Send disarm command. """
        verisure.MY_PAGES.set_alarm_status(code, verisure.MY_PAGES.ALARM_DISARMED)
        _LOGGER.warning('disarming')        
    
    def alarm_arm_home(self, code):
        """ Send arm home command. """
        verisure.MY_PAGES.set_alarm_status(code, verisure.MY_PAGES.ALARM_ARMED_HOME)
        _LOGGER.warning('arming home')        
    
    def alarm_arm_away(self, code):
        """ Send arm away command. """
        verisure.MY_PAGES.set_alarm_status(code, verisure.MY_PAGES.ALARM_ARMED_AWAY)
        _LOGGER.warning('arming away')        
=======
>>>>>>> 614caa33ae4b9fd13bd26436dd4c1dd09ff01119
