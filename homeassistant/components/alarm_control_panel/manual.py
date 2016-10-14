"""
Support for manual alarms.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.manual/
"""
import datetime
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED, CONF_PLATFORM, CONF_NAME,
    CONF_CODE, CONF_PENDING_TIME, CONF_TRIGGER_TIME, CONF_DISARM_AFTER_TRIGGER)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_time

DEFAULT_ALARM_NAME = 'HA Alarm'
DEFAULT_PENDING_TIME = 60
DEFAULT_TRIGGER_TIME = 120
DEFAULT_DISARM_AFTER_TRIGGER = False

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'manual',
    vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_PENDING_TIME, default=DEFAULT_PENDING_TIME):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional(CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_DISARM_AFTER_TRIGGER,
                 default=DEFAULT_DISARM_AFTER_TRIGGER): cv.boolean,
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the manual alarm platform."""
    add_devices([ManualAlarm(
        hass,
        config[CONF_NAME],
        config.get(CONF_CODE),
        config.get(CONF_PENDING_TIME, DEFAULT_PENDING_TIME),
        config.get(CONF_TRIGGER_TIME, DEFAULT_TRIGGER_TIME),
        config.get(CONF_DISARM_AFTER_TRIGGER, DEFAULT_DISARM_AFTER_TRIGGER)
        )])


# pylint: disable=too-many-arguments, too-many-instance-attributes
# pylint: disable=abstract-method
class ManualAlarm(alarm.AlarmControlPanel):
    """
    Represents an alarm status.

    When armed, will be pending for 'pending_time', after that armed.
    When triggered, will be pending for 'trigger_time'. After that will be
    triggered for 'trigger_time', after that we return to the previous state
    or disarm if `disarm_after_trigger` is true.
    """

    def __init__(self, hass, name, code, pending_time,
                 trigger_time, disarm_after_trigger):
        """Initalize the manual alarm panel."""
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._name = name
        self._code = str(code) if code else None
        self._pending_time = datetime.timedelta(seconds=pending_time)
        self._trigger_time = datetime.timedelta(seconds=trigger_time)
        self._disarm_after_trigger = disarm_after_trigger
        self._pre_trigger_state = self._state
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
                if self._disarm_after_trigger:
                    return STATE_ALARM_DISARMED
                else:
                    return self._pre_trigger_state

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
        self._pre_trigger_state = self._state
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
