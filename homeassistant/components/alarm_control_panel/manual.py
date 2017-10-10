"""
Support for manual alarms.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.manual/
"""
import copy
import datetime
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED, STATE_ALARM_PENDING, STATE_ALARM_TRIGGERED,
    CONF_PLATFORM, CONF_NAME, CONF_CODE, CONF_PENDING_TIME, CONF_TRIGGER_TIME,
    CONF_DISARM_AFTER_TRIGGER)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_time

DEFAULT_ALARM_NAME = 'HA Alarm'
DEFAULT_PENDING_TIME = 60
DEFAULT_TRIGGER_TIME = 120
DEFAULT_DISARM_AFTER_TRIGGER = False

SUPPORTED_PENDING_STATES = [STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
                            STATE_ALARM_ARMED_NIGHT, STATE_ALARM_TRIGGERED]

ATTR_POST_PENDING_STATE = 'post_pending_state'


def _state_validator(config):
    config = copy.deepcopy(config)
    for state in SUPPORTED_PENDING_STATES:
        if CONF_PENDING_TIME not in config[state]:
            config[state][CONF_PENDING_TIME] = config[CONF_PENDING_TIME]

    return config


STATE_SETTING_SCHEMA = vol.Schema({
    vol.Optional(CONF_PENDING_TIME):
        vol.All(vol.Coerce(int), vol.Range(min=0))
})


PLATFORM_SCHEMA = vol.Schema(vol.All({
    vol.Required(CONF_PLATFORM): 'manual',
    vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_PENDING_TIME, default=DEFAULT_PENDING_TIME):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional(CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_DISARM_AFTER_TRIGGER,
                 default=DEFAULT_DISARM_AFTER_TRIGGER): cv.boolean,
    vol.Optional(STATE_ALARM_ARMED_AWAY, default={}): STATE_SETTING_SCHEMA,
    vol.Optional(STATE_ALARM_ARMED_HOME, default={}): STATE_SETTING_SCHEMA,
    vol.Optional(STATE_ALARM_ARMED_NIGHT, default={}): STATE_SETTING_SCHEMA,
    vol.Optional(STATE_ALARM_TRIGGERED, default={}): STATE_SETTING_SCHEMA,
}, _state_validator))

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the manual alarm platform."""
    add_devices([ManualAlarm(
        hass,
        config[CONF_NAME],
        config.get(CONF_CODE),
        config.get(CONF_PENDING_TIME, DEFAULT_PENDING_TIME),
        config.get(CONF_TRIGGER_TIME, DEFAULT_TRIGGER_TIME),
        config.get(CONF_DISARM_AFTER_TRIGGER, DEFAULT_DISARM_AFTER_TRIGGER),
        config
        )])


class ManualAlarm(alarm.AlarmControlPanel):
    """
    Representation of an alarm status.

    When armed, will be pending for 'pending_time', after that armed.
    When triggered, will be pending for 'trigger_time'. After that will be
    triggered for 'trigger_time', after that we return to the previous state
    or disarm if `disarm_after_trigger` is true.
    """

    def __init__(self, hass, name, code, pending_time, trigger_time,
                 disarm_after_trigger, config):
        """Init the manual alarm panel."""
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._name = name
        self._code = str(code) if code else None
        self._trigger_time = datetime.timedelta(seconds=trigger_time)
        self._disarm_after_trigger = disarm_after_trigger
        self._pre_trigger_state = self._state
        self._state_ts = None

        self._pending_time_by_state = {}
        for state in SUPPORTED_PENDING_STATES:
            self._pending_time_by_state[state] = datetime.timedelta(
                seconds=config[state][CONF_PENDING_TIME])

    @property
    def should_poll(self):
        """Return the plling state."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state == STATE_ALARM_TRIGGERED and self._trigger_time:
            if self._within_pending_time(self._state):
                return STATE_ALARM_PENDING
            elif (self._state_ts + self._pending_time_by_state[self._state] +
                  self._trigger_time) < dt_util.utcnow():
                if self._disarm_after_trigger:
                    return STATE_ALARM_DISARMED
                else:
                    self._state = self._pre_trigger_state
                    return self._state

        if self._state in SUPPORTED_PENDING_STATES and \
                self._within_pending_time(self._state):
            return STATE_ALARM_PENDING

        return self._state

    def _within_pending_time(self, state):
        pending_time = self._pending_time_by_state[state]
        return self._state_ts + pending_time > dt_util.utcnow()

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
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_HOME):
            return

        self._update_state(STATE_ALARM_ARMED_HOME)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_AWAY):
            return

        self._update_state(STATE_ALARM_ARMED_AWAY)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_NIGHT):
            return

        self._update_state(STATE_ALARM_ARMED_NIGHT)

    def alarm_trigger(self, code=None):
        """Send alarm trigger command. No code needed."""
        self._pre_trigger_state = self._state

        self._update_state(STATE_ALARM_TRIGGERED)

    def _update_state(self, state):
        self._state = state
        self._state_ts = dt_util.utcnow()
        self.schedule_update_ha_state()

        pending_time = self._pending_time_by_state[state]

        if state == STATE_ALARM_TRIGGERED and self._trigger_time:
            track_point_in_time(
                self._hass, self.async_update_ha_state,
                self._state_ts + pending_time)

            track_point_in_time(
                self._hass, self.async_update_ha_state,
                self._state_ts + self._trigger_time + pending_time)
        elif state in SUPPORTED_PENDING_STATES and pending_time:
            track_point_in_time(
                self._hass, self.async_update_ha_state,
                self._state_ts + pending_time)

    def _validate_code(self, code, state):
        """Validate given code."""
        check = self._code is None or code == self._code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
        return check

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}

        if self.state == STATE_ALARM_PENDING:
            state_attr[ATTR_POST_PENDING_STATE] = self._state

        return state_attr
