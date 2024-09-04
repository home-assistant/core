"""Support for manual alarms."""

from __future__ import annotations

import datetime
from typing import Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as ALARM_CONTROL_PANEL_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_TRIGGER_TIME,
    CONF_UNIQUE_ID,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

DOMAIN = "manual"

CONF_ARMING_STATES = "arming_states"
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
    STATE_ALARM_ARMED_VACATION,
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

SUPPORTED_ARMING_STATE_TO_FEATURE = {
    STATE_ALARM_ARMED_AWAY: AlarmControlPanelEntityFeature.ARM_AWAY,
    STATE_ALARM_ARMED_HOME: AlarmControlPanelEntityFeature.ARM_HOME,
    STATE_ALARM_ARMED_NIGHT: AlarmControlPanelEntityFeature.ARM_NIGHT,
    STATE_ALARM_ARMED_VACATION: AlarmControlPanelEntityFeature.ARM_VACATION,
    STATE_ALARM_ARMED_CUSTOM_BYPASS: AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
}

ATTR_PREVIOUS_STATE = "previous_state"
ATTR_NEXT_STATE = "next_state"


def _state_validator(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the state."""
    for state in SUPPORTED_PRETRIGGER_STATES:
        if CONF_DELAY_TIME not in config[state]:
            config[state] = config[state] | {CONF_DELAY_TIME: config[CONF_DELAY_TIME]}
        if CONF_TRIGGER_TIME not in config[state]:
            config[state] = config[state] | {
                CONF_TRIGGER_TIME: config[CONF_TRIGGER_TIME]
            }
    for state in SUPPORTED_ARMING_STATES:
        if CONF_ARMING_TIME not in config[state]:
            config[state] = config[state] | {CONF_ARMING_TIME: config[CONF_ARMING_TIME]}

    return config


def _state_schema(state: str) -> vol.Schema:
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
        ALARM_CONTROL_PANEL_PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
                vol.Optional(CONF_UNIQUE_ID): cv.string,
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
                vol.Optional(
                    CONF_ARMING_STATES, default=SUPPORTED_ARMING_STATES
                ): vol.All(cv.ensure_list, [vol.In(SUPPORTED_ARMING_STATES)]),
                vol.Optional(STATE_ALARM_ARMED_AWAY, default={}): _state_schema(
                    STATE_ALARM_ARMED_AWAY
                ),
                vol.Optional(STATE_ALARM_ARMED_HOME, default={}): _state_schema(
                    STATE_ALARM_ARMED_HOME
                ),
                vol.Optional(STATE_ALARM_ARMED_NIGHT, default={}): _state_schema(
                    STATE_ALARM_ARMED_NIGHT
                ),
                vol.Optional(STATE_ALARM_ARMED_VACATION, default={}): _state_schema(
                    STATE_ALARM_ARMED_VACATION
                ),
                vol.Optional(
                    STATE_ALARM_ARMED_CUSTOM_BYPASS, default={}
                ): _state_schema(STATE_ALARM_ARMED_CUSTOM_BYPASS),
                vol.Optional(STATE_ALARM_DISARMED, default={}): _state_schema(
                    STATE_ALARM_DISARMED
                ),
                vol.Optional(STATE_ALARM_TRIGGERED, default={}): _state_schema(
                    STATE_ALARM_TRIGGERED
                ),
            },
        ),
        _state_validator,
    )
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the manual alarm platform."""
    async_add_entities(
        [
            ManualAlarm(
                hass,
                config[CONF_NAME],
                config.get(CONF_UNIQUE_ID),
                config.get(CONF_CODE),
                config.get(CONF_CODE_TEMPLATE),
                config[CONF_CODE_ARM_REQUIRED],
                config[CONF_DISARM_AFTER_TRIGGER],
                config,
            )
        ]
    )


class ManualAlarm(AlarmControlPanelEntity, RestoreEntity):
    """Representation of an alarm status.

    When armed, will be arming for 'arming_time', after that armed.
    When triggered, will be pending for the triggering state's 'delay_time'.
    After that will be triggered for 'trigger_time', after that we return to
    the previous state or disarm if `disarm_after_trigger` is true.
    A trigger_time of zero disables the alarm_trigger service.
    """

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str | None,
        code: str | None,
        code_template: Template | None,
        code_arm_required: bool,
        disarm_after_trigger: bool,
        config: dict[str, Any],
    ) -> None:
        """Init the manual alarm panel."""
        self._state = STATE_ALARM_DISARMED
        self._hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._code = code_template or code or None
        self._attr_code_arm_required = code_arm_required
        self._disarm_after_trigger = disarm_after_trigger
        self._previous_state = self._state
        self._state_ts: datetime.datetime = dt_util.utcnow()

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

        self._attr_supported_features = AlarmControlPanelEntityFeature.TRIGGER
        for arming_state in config.get(CONF_ARMING_STATES, SUPPORTED_ARMING_STATES):
            self._attr_supported_features |= SUPPORTED_ARMING_STATE_TO_FEATURE[
                arming_state
            ]

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self._state == STATE_ALARM_TRIGGERED:
            if self._within_pending_time(self._state):
                return STATE_ALARM_PENDING
            trigger_time: datetime.timedelta = self._trigger_time_by_state[
                self._previous_state
            ]
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
    def _active_state(self) -> str:
        """Get the current state."""
        if self.state in (STATE_ALARM_PENDING, STATE_ALARM_ARMING):
            return self._previous_state
        return self._state

    def _arming_time(self, state: str) -> datetime.timedelta:
        """Get the arming time."""
        arming_time: datetime.timedelta = self._arming_time_by_state[state]
        return arming_time

    def _pending_time(self, state: str) -> datetime.timedelta:
        """Get the pending time."""
        delay_time: datetime.timedelta = self._delay_time_by_state[self._previous_state]
        return delay_time

    def _within_arming_time(self, state: str) -> bool:
        """Get if the action is in the arming time window."""
        return self._state_ts + self._arming_time(state) > dt_util.utcnow()

    def _within_pending_time(self, state: str) -> bool:
        """Get if the action is in the pending time window."""
        return self._state_ts + self._pending_time(state) > dt_util.utcnow()

    @property
    def code_format(self) -> CodeFormat | None:
        """Return one or more digits/characters."""
        if self._code is None:
            return None
        if isinstance(self._code, str) and self._code.isdigit():
            return CodeFormat.NUMBER
        return CodeFormat.TEXT

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._async_validate_code(code, STATE_ALARM_DISARMED)
        self._state = STATE_ALARM_DISARMED
        self._state_ts = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._async_validate_code(code, STATE_ALARM_ARMED_HOME)
        self._async_update_state(STATE_ALARM_ARMED_HOME)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._async_validate_code(code, STATE_ALARM_ARMED_AWAY)
        self._async_update_state(STATE_ALARM_ARMED_AWAY)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self._async_validate_code(code, STATE_ALARM_ARMED_NIGHT)
        self._async_update_state(STATE_ALARM_ARMED_NIGHT)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        self._async_validate_code(code, STATE_ALARM_ARMED_VACATION)
        self._async_update_state(STATE_ALARM_ARMED_VACATION)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command."""
        self._async_validate_code(code, STATE_ALARM_ARMED_CUSTOM_BYPASS)
        self._async_update_state(STATE_ALARM_ARMED_CUSTOM_BYPASS)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command.

        No code needed, a trigger time of zero for the current state
        disables the alarm.
        """
        if not self._trigger_time_by_state[self._active_state]:
            return
        self._async_update_state(STATE_ALARM_TRIGGERED)

    def _async_update_state(self, state: str) -> None:
        """Update the state."""
        if self._state == state:
            return

        self._previous_state = self._state
        self._state = state
        self._state_ts = dt_util.utcnow()
        self.async_write_ha_state()
        self._async_set_state_update_events()

    def _async_set_state_update_events(self) -> None:
        state = self._state
        if state == STATE_ALARM_TRIGGERED:
            pending_time = self._pending_time(state)
            async_track_point_in_time(
                self._hass, self.async_scheduled_update, self._state_ts + pending_time
            )

            trigger_time = self._trigger_time_by_state[self._previous_state]
            async_track_point_in_time(
                self._hass,
                self.async_scheduled_update,
                self._state_ts + pending_time + trigger_time,
            )
        elif state in SUPPORTED_ARMING_STATES:
            arming_time = self._arming_time(state)
            if arming_time:
                async_track_point_in_time(
                    self._hass,
                    self.async_scheduled_update,
                    self._state_ts + arming_time,
                )

    def _async_validate_code(self, code: str | None, state: str) -> None:
        """Validate given code."""
        if (
            state != STATE_ALARM_DISARMED and not self.code_arm_required
        ) or self._code is None:
            return

        if isinstance(self._code, str):
            alarm_code = self._code
        else:
            alarm_code = self._code.async_render(
                parse_result=False, from_state=self._state, to_state=state
            )

        if not alarm_code or code == alarm_code:
            return

        raise ServiceValidationError(
            "Invalid alarm code provided",
            translation_domain=DOMAIN,
            translation_key="invalid_code",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.state in (STATE_ALARM_PENDING, STATE_ALARM_ARMING):
            prev_state: str | None = self._previous_state
            state: str | None = self._state
        elif self.state == STATE_ALARM_TRIGGERED:
            prev_state = self._previous_state
            state = None
        else:
            prev_state = None
            state = None
        return {ATTR_PREVIOUS_STATE: prev_state, ATTR_NEXT_STATE: state}

    @callback
    def async_scheduled_update(self, now: datetime.datetime) -> None:
        """Update state at a scheduled point in time."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            self._state_ts = state.last_updated
            if next_state := state.attributes.get(ATTR_NEXT_STATE):
                # If in arming or pending state we record the transition,
                # not the current state
                self._state = next_state
            else:
                self._state = state.state

            if prev_state := state.attributes.get(ATTR_PREVIOUS_STATE):
                self._previous_state = prev_state
                self._async_set_state_update_events()
