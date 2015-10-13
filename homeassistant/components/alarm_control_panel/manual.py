"""
homeassistant.components.alarm_control_panel.manual

Configuration:

alarm_control_panel:
  platform: manual
  name: "HA Alarm"
  code: "mySecretCode"
  pending_time: 60
  trigger_time: 120

Variables:

name
*Optional
The name of the alarm. Default is 'HA Alarm'.

code
*Optional
If defined, specifies a code to arm or disarm the alarm in the frontend.

pending_time
*Optional
The time in seconds of the pending time before arming the alarm.
Default is 60 seconds.

trigger_time
*Optional
The time in seconds of the trigger time in which the alarm is firing.
Default is 120 seconds.

"""

import logging
import datetime
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.helpers.event import track_point_in_time
import homeassistant.util.dt as dt_util

from homeassistant.const import (
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []

DEFAULT_ALARM_NAME = 'HA Alarm'
DEFAULT_PENDING_TIME = 60
DEFAULT_TRIGGER_TIME = 120


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the manual alarm platform. """

    add_devices([ManualAlarm(
        hass,
        config.get('name', DEFAULT_ALARM_NAME),
        config.get('code'),
        config.get('pending_time', DEFAULT_PENDING_TIME),
        config.get('trigger_time', DEFAULT_TRIGGER_TIME),
        )])


# pylint: disable=too-many-arguments, too-many-instance-attributes
# pylint: disable=abstract-method
class ManualAlarm(alarm.AlarmControlPanel):
    """ represents an alarm status within home assistant. """

    def __init__(self, hass, name, code, pending_time, trigger_time):
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._name = name
        self._code = code
        self._pending_time = datetime.timedelta(seconds=pending_time)
        self._trigger_time = datetime.timedelta(seconds=trigger_time)
        self._state_ts = None
        self._pending_to = None

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def code_format(self):
        """ One or more characters """
        return None if self._code is None else '.+'

    def update_state(self, state, pending_to):
        """ changes between state with delay """
        self._state = state
        self._state_ts = dt_util.utcnow()
        self._pending_to = pending_to
        self.update_ha_state()

    def alarm_disarm(self, code=None):
        """ Send disarm command. """
        if code == str(self._code) or self.code_format is None:
            self.update_state(STATE_ALARM_DISARMED, None)
        else:
            _LOGGER.warning("Wrong code entered while disarming!")

    def alarm_arm_home(self, code=None):
        """ Send arm home command. """
        if code == str(self._code) or self.code_format is None:
            self.update_state(STATE_ALARM_PENDING, STATE_ALARM_ARMED_HOME)

            def delayed_alarm_arm_home(event_time):
                """ callback for delayed action """
                if self._pending_to == STATE_ALARM_ARMED_HOME and \
                   dt_util.utcnow() - self._state_ts >= self._pending_time:
                    self.update_state(STATE_ALARM_ARMED_HOME, None)
            track_point_in_time(
                self._hass, delayed_alarm_arm_home,
                dt_util.utcnow() + self._pending_time)
        else:
            _LOGGER.warning("Wrong code entered while arming home!")

    def alarm_arm_away(self, code=None):
        """ Send arm away command. """
        if code == str(self._code) or self.code_format is None:
            self.update_state(STATE_ALARM_PENDING, STATE_ALARM_ARMED_AWAY)

            def delayed_alarm_arm_away(event_time):
                """ callback for delayed action """
                if self._pending_to == STATE_ALARM_ARMED_AWAY and \
                   dt_util.utcnow() - self._state_ts >= self._pending_time:
                    self.update_state(STATE_ALARM_ARMED_AWAY, None)
            track_point_in_time(
                self._hass, delayed_alarm_arm_away,
                dt_util.utcnow() + self._pending_time)
        else:
            _LOGGER.warning("Wrong code entered while arming away!")

    def alarm_trigger(self, code=None):
        """ Send alarm trigger command. No code needed. """
        self.update_state(STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)

        def delayed_alarm_trigger(event_time):
            """ callback for delayed action """
            if self._pending_to == STATE_ALARM_TRIGGERED and \
               dt_util.utcnow() - self._state_ts >= self._pending_time:
                self.update_state(STATE_ALARM_TRIGGERED, STATE_ALARM_DISARMED)

                def delayed_alarm_disarm(event_time):
                    """ callback for delayed action """
                    if self._pending_to == STATE_ALARM_DISARMED and \
                       dt_util.utcnow() - self._state_ts >= self._trigger_time:
                        self.update_state(STATE_ALARM_DISARMED, None)
                track_point_in_time(
                    self._hass, delayed_alarm_disarm,
                    dt_util.utcnow() + self._trigger_time)
        track_point_in_time(
            self._hass, delayed_alarm_trigger,
            dt_util.utcnow() + self._pending_time)
