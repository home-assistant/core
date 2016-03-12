"""
Support for manual alarms.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.manual/
"""
import datetime
import logging

import homeassistant.components.alarm_control_panel as alarm
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED)
from homeassistant.helpers.event import track_point_in_time

_LOGGER = logging.getLogger(__name__)

DEFAULT_ALARM_NAME = 'HA Alarm'
DEFAULT_PENDING_TIME = 60
DEFAULT_TRIGGER_TIME = 120


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the manual alarm platform."""
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
    """
    Represents an alarm status.

    When armed, will be pending for 'pending_time', after that armed.
    When triggered, will be pending for 'trigger_time'. After that will be
    triggered for 'trigger_time', after that we return to disarmed.
    """

    def __init__(self, hass, name, code, pending_time, trigger_time):
        """Initalize the manual alarm panel."""
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._name = name
        self._code = str(code) if code else None
        self._pending_time = datetime.timedelta(seconds=pending_time)
        self._trigger_time = datetime.timedelta(seconds=trigger_time)
        self._state_ts = None

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state in (STATE_ALARM_ARMED_HOME,
                           STATE_ALARM_ARMED_AWAY) and \
           self._pending_time and self._state_ts + self._pending_time > \
           dt_util.utcnow():
            return STATE_ALARM_PENDING

        if self._state == STATE_ALARM_TRIGGERED and self._trigger_time:
            if self._state_ts + self._pending_time > dt_util.utcnow():
                return STATE_ALARM_PENDING
            elif (self._state_ts + self._pending_time +
                  self._trigger_time) < dt_util.utcnow():
                return STATE_ALARM_DISARMED

        return self._state

    @property
    def code_format(self):
        """One or more characters."""
        return None if self._code is None else '.+'

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, STATE_ALARM_DISARMED):
            return

        self._state = STATE_ALARM_DISARMED
        self._state_ts = dt_util.utcnow()
        self.update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_HOME):
            return

        self._state = STATE_ALARM_ARMED_HOME
        self._state_ts = dt_util.utcnow()
        self.update_ha_state()

        if self._pending_time:
            track_point_in_time(
                self._hass, self.update_ha_state,
                self._state_ts + self._pending_time)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_AWAY):
            return

        self._state = STATE_ALARM_ARMED_AWAY
        self._state_ts = dt_util.utcnow()
        self.update_ha_state()

        if self._pending_time:
            track_point_in_time(
                self._hass, self.update_ha_state,
                self._state_ts + self._pending_time)

    def alarm_trigger(self, code=None):
        """Send alarm trigger command. No code needed."""
        self._state = STATE_ALARM_TRIGGERED
        self._state_ts = dt_util.utcnow()
        self.update_ha_state()

        if self._trigger_time:
            track_point_in_time(
                self._hass, self.update_ha_state,
                self._state_ts + self._pending_time)

            track_point_in_time(
                self._hass, self.update_ha_state,
                self._state_ts + self._pending_time + self._trigger_time)

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning('Invalid code given for %s', state)
        return check
