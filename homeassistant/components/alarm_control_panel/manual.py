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
    STATE_ALARM_ARMED_CUSTOM_BYPASS, STATE_ALARM_DISARMED, STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED, CONF_PLATFORM, CONF_NAME, CONF_CODE,
    CONF_DELAY_TIME, CONF_PENDING_TIME, CONF_TRIGGER_TIME,
    CONF_DISARM_AFTER_TRIGGER)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_time

CONF_CODE_TEMPLATE = 'code_template'

DEFAULT_ALARM_NAME = 'HA Alarm'
DEFAULT_DELAY_TIME = datetime.timedelta(seconds=0)
DEFAULT_PENDING_TIME = datetime.timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = datetime.timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False

SUPPORTED_STATES = [STATE_ALARM_DISARMED, STATE_ALARM_ARMED_AWAY,
                    STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
                    STATE_ALARM_ARMED_CUSTOM_BYPASS, STATE_ALARM_TRIGGERED]

SUPPORTED_PRETRIGGER_STATES = [state for state in SUPPORTED_STATES
                               if state != STATE_ALARM_TRIGGERED]

SUPPORTED_PENDING_STATES = [state for state in SUPPORTED_STATES
                            if state != STATE_ALARM_DISARMED]

ATTR_PRE_PENDING_STATE = 'pre_pending_state'
ATTR_POST_PENDING_STATE = 'post_pending_state'


def _state_validator(config):
    config = copy.deepcopy(config)
    for state in SUPPORTED_PRETRIGGER_STATES:
        if CONF_DELAY_TIME not in config[state]:
            config[state][CONF_DELAY_TIME] = config[CONF_DELAY_TIME]
        if CONF_TRIGGER_TIME not in config[state]:
            config[state][CONF_TRIGGER_TIME] = config[CONF_TRIGGER_TIME]
    for state in SUPPORTED_PENDING_STATES:
        if CONF_PENDING_TIME not in config[state]:
            config[state][CONF_PENDING_TIME] = config[CONF_PENDING_TIME]

    return config


def _state_schema(state):
    schema = {}
    if state in SUPPORTED_PRETRIGGER_STATES:
        schema[vol.Optional(CONF_DELAY_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta)
        schema[vol.Optional(CONF_TRIGGER_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta)
    if state in SUPPORTED_PENDING_STATES:
        schema[vol.Optional(CONF_PENDING_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta)
    return vol.Schema(schema)


PLATFORM_SCHEMA = vol.Schema(vol.All({
    vol.Required(CONF_PLATFORM): 'manual',
    vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
    vol.Exclusive(CONF_CODE, 'code validation'): cv.string,
    vol.Exclusive(CONF_CODE_TEMPLATE, 'code validation'): cv.template,
    vol.Optional(CONF_DELAY_TIME, default=DEFAULT_DELAY_TIME):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_PENDING_TIME, default=DEFAULT_PENDING_TIME):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DISARM_AFTER_TRIGGER,
                 default=DEFAULT_DISARM_AFTER_TRIGGER): cv.boolean,
    vol.Optional(STATE_ALARM_ARMED_AWAY, default={}):
        _state_schema(STATE_ALARM_ARMED_AWAY),
    vol.Optional(STATE_ALARM_ARMED_HOME, default={}):
        _state_schema(STATE_ALARM_ARMED_HOME),
    vol.Optional(STATE_ALARM_ARMED_NIGHT, default={}):
        _state_schema(STATE_ALARM_ARMED_NIGHT),
    vol.Optional(STATE_ALARM_ARMED_CUSTOM_BYPASS, default={}):
        _state_schema(STATE_ALARM_ARMED_CUSTOM_BYPASS),
    vol.Optional(STATE_ALARM_DISARMED, default={}):
        _state_schema(STATE_ALARM_DISARMED),
    vol.Optional(STATE_ALARM_TRIGGERED, default={}):
        _state_schema(STATE_ALARM_TRIGGERED),
}, _state_validator))

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the manual alarm platform."""
    add_devices([ManualAlarm(
        hass,
        config[CONF_NAME],
        config.get(CONF_CODE),
        config.get(CONF_CODE_TEMPLATE),
        config.get(CONF_DISARM_AFTER_TRIGGER, DEFAULT_DISARM_AFTER_TRIGGER),
        config
        )])


class ManualAlarm(alarm.AlarmControlPanel):
    """
    Representation of an alarm status.

    When armed, will be pending for 'pending_time', after that armed.
    When triggered, will be pending for the triggering state's 'delay_time'
    plus the triggered state's 'pending_time'.
    After that will be triggered for 'trigger_time', after that we return to
    the previous state or disarm if `disarm_after_trigger` is true.
    A trigger_time of zero disables the alarm_trigger service.
    """

    def __init__(self, hass, name, code, code_template,
                 disarm_after_trigger, config):
        """Init the manual alarm panel."""
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._name = name
        if code_template:
            self._code = code_template
            self._code.hass = hass
        else:
            self._code = code or None
        self._disarm_after_trigger = disarm_after_trigger
        self._previous_state = self._state
        self._state_ts = None

        self._delay_time_by_state = {
            state: config[state][CONF_DELAY_TIME]
            for state in SUPPORTED_PRETRIGGER_STATES}
        self._trigger_time_by_state = {
            state: config[state][CONF_TRIGGER_TIME]
            for state in SUPPORTED_PRETRIGGER_STATES}
        self._pending_time_by_state = {
            state: config[state][CONF_PENDING_TIME]
            for state in SUPPORTED_PENDING_STATES}

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
        if self._state == STATE_ALARM_TRIGGERED:
            if self._within_pending_time(self._state):
                return STATE_ALARM_PENDING
            trigger_time = self._trigger_time_by_state[self._previous_state]
            if (self._state_ts + self._pending_time(self._state) +
                    trigger_time) < dt_util.utcnow():
                if self._disarm_after_trigger:
                    return STATE_ALARM_DISARMED
                else:
                    self._state = self._previous_state
                    return self._state

        if self._state in SUPPORTED_PENDING_STATES and \
                self._within_pending_time(self._state):
            return STATE_ALARM_PENDING

        return self._state

    @property
    def _active_state(self):
        if self.state == STATE_ALARM_PENDING:
            return self._previous_state
        else:
            return self._state

    def _pending_time(self, state):
        pending_time = self._pending_time_by_state[state]
        if state == STATE_ALARM_TRIGGERED:
            pending_time += self._delay_time_by_state[self._previous_state]
        return pending_time

    def _within_pending_time(self, state):
        return self._state_ts + self._pending_time(state) > dt_util.utcnow()

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

    def alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        if not self._validate_code(code, STATE_ALARM_ARMED_CUSTOM_BYPASS):
            return

        self._update_state(STATE_ALARM_ARMED_CUSTOM_BYPASS)

    def alarm_trigger(self, code=None):
        """
        Send alarm trigger command.

        No code needed, a trigger time of zero for the current state
        disables the alarm.
        """
        if not self._trigger_time_by_state[self._active_state]:
            return
        self._update_state(STATE_ALARM_TRIGGERED)

    def _update_state(self, state):
        if self._state == state:
            return

        self._previous_state = self._state
        self._state = state
        self._state_ts = dt_util.utcnow()
        self.schedule_update_ha_state()

        pending_time = self._pending_time(state)
        if state == STATE_ALARM_TRIGGERED:
            track_point_in_time(
                self._hass, self.async_update_ha_state,
                self._state_ts + pending_time)

            trigger_time = self._trigger_time_by_state[self._previous_state]
            track_point_in_time(
                self._hass, self.async_update_ha_state,
                self._state_ts + pending_time + trigger_time)
        elif state in SUPPORTED_PENDING_STATES and pending_time:
            track_point_in_time(
                self._hass, self.async_update_ha_state,
                self._state_ts + pending_time)

    def _validate_code(self, code, state):
        """Validate given code."""
        if self._code is None:
            return True
        if isinstance(self._code, str):
            alarm_code = self._code
        else:
            alarm_code = self._code.render(from_state=self._state,
                                           to_state=state)
        check = not alarm_code or code == alarm_code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
        return check

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}

        if self.state == STATE_ALARM_PENDING:
            state_attr[ATTR_PRE_PENDING_STATE] = self._previous_state
            state_attr[ATTR_POST_PENDING_STATE] = self._state

        return state_attr
