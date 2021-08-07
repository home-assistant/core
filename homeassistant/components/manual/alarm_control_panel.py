"""Support for manual alarms."""
import copy
import datetime
import logging
import re

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_TRIGGER_TIME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_CODE_TEMPLATE = "code_template"
CONF_CODE_ARM_REQUIRED = "code_arm_required"

DEFAULT_ALARM_NAME = "HA Alarm"
DEFAULT_DELAY_TIME = datetime.timedelta(seconds=60)
DEFAULT_ARMING_TIME = datetime.timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = datetime.timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False

SUPPORTED_STATES = [
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_TRIGGERED,
]

SUPPORTED_PRETRIGGER_STATES = [
    state for state in SUPPORTED_STATES if state != STATE_ALARM_TRIGGERED
]

SUPPORTED_ARMING_STATES = [
    state
    for state in SUPPORTED_STATES
    if state not in (STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED)
]

ATTR_PREVIOUS_STATE = "previous_state"
ATTR_NEXT_STATE = "next_state"


def _state_validator(config):
    """Validate the state."""
    config = copy.deepcopy(config)
    for state in SUPPORTED_PRETRIGGER_STATES:
        if CONF_DELAY_TIME not in config[state]:
            config[state][CONF_DELAY_TIME] = config[CONF_DELAY_TIME]
        if CONF_TRIGGER_TIME not in config[state]:
            config[state][CONF_TRIGGER_TIME] = config[CONF_TRIGGER_TIME]
    for state in SUPPORTED_ARMING_STATES:
        if CONF_ARMING_TIME not in config[state]:
            config[state][CONF_ARMING_TIME] = config[CONF_ARMING_TIME]

    return config


def _state_schema(state):
    """Validate the state."""
    schema = {}
    if state in SUPPORTED_PRETRIGGER_STATES:
        schema[vol.Optional(CONF_DELAY_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta
        )
        schema[vol.Optional(CONF_TRIGGER_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta
        )
    if state in SUPPORTED_ARMING_STATES:
        schema[vol.Optional(CONF_ARMING_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta
        )
    return vol.Schema(schema)


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_PLATFORM): "manual",
            vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
            vol.Exclusive(CONF_CODE, "code validation"): cv.string,
            vol.Exclusive(CONF_CODE_TEMPLATE, "code validation"): cv.template,
            vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
            vol.Optional(CONF_DELAY_TIME, default=DEFAULT_DELAY_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(CONF_ARMING_TIME, default=DEFAULT_ARMING_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
            vol.Optional(
                CONF_DISARM_AFTER_TRIGGER, default=DEFAULT_DISARM_AFTER_TRIGGER
            ): cv.boolean,
            vol.Optional(STATE_ALARM_ARMED_AWAY, default={}): _state_schema(
                STATE_ALARM_ARMED_AWAY
            ),
            vol.Optional(STATE_ALARM_ARMED_HOME, default={}): _state_schema(
                STATE_ALARM_ARMED_HOME
            ),
            vol.Optional(STATE_ALARM_ARMED_NIGHT, default={}): _state_schema(
                STATE_ALARM_ARMED_NIGHT
            ),
            vol.Optional(STATE_ALARM_ARMED_CUSTOM_BYPASS, default={}): _state_schema(
                STATE_ALARM_ARMED_CUSTOM_BYPASS
            ),
            vol.Optional(STATE_ALARM_DISARMED, default={}): _state_schema(
                STATE_ALARM_DISARMED
            ),
            vol.Optional(STATE_ALARM_TRIGGERED, default={}): _state_schema(
                STATE_ALARM_TRIGGERED
            ),
        },
        _state_validator,
    )
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the manual alarm platform."""
    add_entities(
        [
            ManualAlarm(
                hass,
                config[CONF_NAME],
                config.get(CONF_CODE),
                config.get(CONF_CODE_TEMPLATE),
                config.get(CONF_CODE_ARM_REQUIRED),
                config.get(CONF_DISARM_AFTER_TRIGGER, DEFAULT_DISARM_AFTER_TRIGGER),
                config,
            )
        ]
    )


class ManualAlarm(alarm.AlarmControlPanelEntity, RestoreEntity):
    """
    Representation of an alarm status.

    When armed, will be arming for 'arming_time', after that armed.
    When triggered, will be pending for the triggering state's 'delay_time'.
    After that will be triggered for 'trigger_time', after that we return to
    the previous state or disarm if `disarm_after_trigger` is true.
    A trigger_time of zero disables the alarm_trigger service.
    """

    def __init__(
        self,
        hass,
        name,
        code,
        code_template,
        code_arm_required,
        disarm_after_trigger,
        config,
    ):
        """Init the manual alarm panel."""
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._name = name
        if code_template:
            self._code = code_template
            self._code.hass = hass
        else:
            self._code = code or None
        self._code_arm_required = code_arm_required
        self._disarm_after_trigger = disarm_after_trigger
        self._previous_state = self._state
        self._state_ts = None

        self._delay_time_by_state = {
            state: config[state][CONF_DELAY_TIME]
            for state in SUPPORTED_PRETRIGGER_STATES
        }
        self._trigger_time_by_state = {
            state: config[state][CONF_TRIGGER_TIME]
            for state in SUPPORTED_PRETRIGGER_STATES
        }
        self._arming_time_by_state = {
            state: config[state][CONF_ARMING_TIME] for state in SUPPORTED_ARMING_STATES
        }

    @property
    def should_poll(self):
        """Return the polling state."""
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
            if (
                self._state_ts + self._pending_time(self._state) + trigger_time
            ) < dt_util.utcnow():
                if self._disarm_after_trigger:
                    return STATE_ALARM_DISARMED
                self._state = self._previous_state
                return self._state

        if self._state in SUPPORTED_ARMING_STATES and self._within_arming_time(
            self._state
        ):
            return STATE_ALARM_ARMING

        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return (
            SUPPORT_ALARM_ARM_HOME
            | SUPPORT_ALARM_ARM_AWAY
            | SUPPORT_ALARM_ARM_NIGHT
            | SUPPORT_ALARM_TRIGGER
            | SUPPORT_ALARM_ARM_CUSTOM_BYPASS
        )

    @property
    def _active_state(self):
        """Get the current state."""
        if self.state in (STATE_ALARM_PENDING, STATE_ALARM_ARMING):
            return self._previous_state
        return self._state

    def _arming_time(self, state):
        """Get the arming time."""
        return self._arming_time_by_state[state]

    def _pending_time(self, state):
        """Get the pending time."""
        return self._delay_time_by_state[self._previous_state]

    def _within_arming_time(self, state):
        """Get if the action is in the arming time window."""
        return self._state_ts + self._arming_time(state) > dt_util.utcnow()

    def _within_pending_time(self, state):
        """Get if the action is in the pending time window."""
        return self._state_ts + self._pending_time(state) > dt_util.utcnow()

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and re.search("^\\d+$", self._code):
            return alarm.FORMAT_NUMBER
        return alarm.FORMAT_TEXT

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return self._code_arm_required

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._validate_code(code, STATE_ALARM_DISARMED):
            return

        self._state = STATE_ALARM_DISARMED
        self._state_ts = dt_util.utcnow()
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if self._code_arm_required and not self._validate_code(
            code, STATE_ALARM_ARMED_HOME
        ):
            return

        self._update_state(STATE_ALARM_ARMED_HOME)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if self._code_arm_required and not self._validate_code(
            code, STATE_ALARM_ARMED_AWAY
        ):
            return

        self._update_state(STATE_ALARM_ARMED_AWAY)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        if self._code_arm_required and not self._validate_code(
            code, STATE_ALARM_ARMED_NIGHT
        ):
            return

        self._update_state(STATE_ALARM_ARMED_NIGHT)

    def alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        if self._code_arm_required and not self._validate_code(
            code, STATE_ALARM_ARMED_CUSTOM_BYPASS
        ):
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
        """Update the state."""
        if self._state == state:
            return

        self._previous_state = self._state
        self._state = state
        self._state_ts = dt_util.utcnow()
        self.schedule_update_ha_state()

        if state == STATE_ALARM_TRIGGERED:
            pending_time = self._pending_time(state)
            track_point_in_time(
                self._hass, self.async_scheduled_update, self._state_ts + pending_time
            )

            trigger_time = self._trigger_time_by_state[self._previous_state]
            track_point_in_time(
                self._hass,
                self.async_scheduled_update,
                self._state_ts + pending_time + trigger_time,
            )
        elif state in SUPPORTED_ARMING_STATES:
            arming_time = self._arming_time(state)
            if arming_time:
                track_point_in_time(
                    self._hass,
                    self.async_scheduled_update,
                    self._state_ts + arming_time,
                )

    def _validate_code(self, code, state):
        """Validate given code."""
        if self._code is None:
            return True
        if isinstance(self._code, str):
            alarm_code = self._code
        else:
            alarm_code = self._code.render(
                parse_result=False, from_state=self._state, to_state=state
            )
        check = not alarm_code or code == alarm_code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
        return check

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.state == STATE_ALARM_PENDING or self.state == STATE_ALARM_ARMING:
            return {
                ATTR_PREVIOUS_STATE: self._previous_state,
                ATTR_NEXT_STATE: self._state,
            }
        return {}

    @callback
    def async_scheduled_update(self, now):
        """Update state at a scheduled point in time."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            if (
                (
                    state.state == STATE_ALARM_PENDING
                    or state.state == STATE_ALARM_ARMING
                )
                and hasattr(state, "attributes")
                and state.attributes[ATTR_PREVIOUS_STATE]
            ):
                # If in arming or pending state, we return to the ATTR_PREVIOUS_STATE
                self._state = state.attributes[ATTR_PREVIOUS_STATE]
                self._state_ts = dt_util.utcnow()
            else:
                self._state = state.state
                self._state_ts = state.last_updated
