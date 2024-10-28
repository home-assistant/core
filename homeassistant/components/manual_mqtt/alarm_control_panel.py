"""Support for manual alarms controllable via MQTT."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_PENDING_TIME,
    CONF_PLATFORM,
    CONF_TRIGGER_TIME,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_CODE_TEMPLATE = "code_template"
CONF_CODE_ARM_REQUIRED = "code_arm_required"

CONF_PAYLOAD_DISARM = "payload_disarm"
CONF_PAYLOAD_ARM_HOME = "payload_arm_home"
CONF_PAYLOAD_ARM_AWAY = "payload_arm_away"
CONF_PAYLOAD_ARM_NIGHT = "payload_arm_night"
CONF_PAYLOAD_ARM_VACATION = "payload_arm_vacation"
CONF_PAYLOAD_ARM_CUSTOM_BYPASS = "payload_arm_custom_bypass"

CONF_ALARM_ARMED_AWAY = "armed_away"
CONF_ALARM_ARMED_CUSTOM_BYPASS = "armed_custom_bypass"
CONF_ALARM_ARMED_HOME = "armed_home"
CONF_ALARM_ARMED_NIGHT = "armed_night"
CONF_ALARM_ARMED_VACATION = "armed_vacation"
CONF_ALARM_DISARMED = "disarmed"
CONF_ALARM_PENDING = "pending"
CONF_ALARM_TRIGGERED = "triggered"

DEFAULT_ALARM_NAME = "HA Alarm"
DEFAULT_DELAY_TIME = datetime.timedelta(seconds=0)
DEFAULT_PENDING_TIME = datetime.timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = datetime.timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False
DEFAULT_ARM_AWAY = "ARM_AWAY"
DEFAULT_ARM_HOME = "ARM_HOME"
DEFAULT_ARM_NIGHT = "ARM_NIGHT"
DEFAULT_ARM_VACATION = "ARM_VACATION"
DEFAULT_ARM_CUSTOM_BYPASS = "ARM_CUSTOM_BYPASS"
DEFAULT_DISARM = "DISARM"

SUPPORTED_STATES = [
    AlarmControlPanelState.DISARMED,
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_HOME,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_VACATION,
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    AlarmControlPanelState.TRIGGERED,
]

SUPPORTED_PRETRIGGER_STATES = [
    state for state in SUPPORTED_STATES if state != AlarmControlPanelState.TRIGGERED
]

SUPPORTED_PENDING_STATES = [
    state for state in SUPPORTED_STATES if state != AlarmControlPanelState.DISARMED
]

ATTR_PRE_PENDING_STATE = "pre_pending_state"
ATTR_POST_PENDING_STATE = "post_pending_state"


def _state_validator(config):
    """Validate the state."""
    for state in SUPPORTED_PRETRIGGER_STATES:
        if CONF_DELAY_TIME not in config[state]:
            config[state] = config[state] | {CONF_DELAY_TIME: config[CONF_DELAY_TIME]}
        if CONF_TRIGGER_TIME not in config[state]:
            config[state] = config[state] | {
                CONF_TRIGGER_TIME: config[CONF_TRIGGER_TIME]
            }
    for state in SUPPORTED_PENDING_STATES:
        if CONF_PENDING_TIME not in config[state]:
            config[state] = config[state] | {
                CONF_PENDING_TIME: config[CONF_PENDING_TIME]
            }

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
    if state in SUPPORTED_PENDING_STATES:
        schema[vol.Optional(CONF_PENDING_TIME)] = vol.All(
            cv.time_period, cv.positive_timedelta
        )
    return vol.Schema(schema)


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        mqtt.config.MQTT_BASE_SCHEMA.extend(
            {
                vol.Required(CONF_PLATFORM): "manual_mqtt",
                vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
                vol.Exclusive(CONF_CODE, "code validation"): cv.string,
                vol.Exclusive(CONF_CODE_TEMPLATE, "code validation"): cv.template,
                vol.Optional(CONF_DELAY_TIME, default=DEFAULT_DELAY_TIME): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
                vol.Optional(CONF_PENDING_TIME, default=DEFAULT_PENDING_TIME): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
                vol.Optional(CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
                vol.Optional(
                    CONF_DISARM_AFTER_TRIGGER, default=DEFAULT_DISARM_AFTER_TRIGGER
                ): cv.boolean,
                vol.Optional(CONF_ALARM_ARMED_AWAY, default={}): _state_schema(
                    AlarmControlPanelState.ARMED_AWAY
                ),
                vol.Optional(CONF_ALARM_ARMED_HOME, default={}): _state_schema(
                    AlarmControlPanelState.ARMED_HOME
                ),
                vol.Optional(CONF_ALARM_ARMED_NIGHT, default={}): _state_schema(
                    AlarmControlPanelState.ARMED_NIGHT
                ),
                vol.Optional(CONF_ALARM_ARMED_VACATION, default={}): _state_schema(
                    AlarmControlPanelState.ARMED_VACATION
                ),
                vol.Optional(CONF_ALARM_ARMED_CUSTOM_BYPASS, default={}): _state_schema(
                    AlarmControlPanelState.ARMED_CUSTOM_BYPASS
                ),
                vol.Optional(CONF_ALARM_DISARMED, default={}): _state_schema(
                    AlarmControlPanelState.DISARMED
                ),
                vol.Optional(CONF_ALARM_TRIGGERED, default={}): _state_schema(
                    AlarmControlPanelState.TRIGGERED
                ),
                vol.Required(mqtt.CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
                vol.Required(mqtt.CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
                vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
                vol.Optional(
                    CONF_PAYLOAD_ARM_AWAY, default=DEFAULT_ARM_AWAY
                ): cv.string,
                vol.Optional(
                    CONF_PAYLOAD_ARM_HOME, default=DEFAULT_ARM_HOME
                ): cv.string,
                vol.Optional(
                    CONF_PAYLOAD_ARM_NIGHT, default=DEFAULT_ARM_NIGHT
                ): cv.string,
                vol.Optional(
                    CONF_PAYLOAD_ARM_VACATION, default=DEFAULT_ARM_VACATION
                ): cv.string,
                vol.Optional(
                    CONF_PAYLOAD_ARM_CUSTOM_BYPASS, default=DEFAULT_ARM_CUSTOM_BYPASS
                ): cv.string,
                vol.Optional(CONF_PAYLOAD_DISARM, default=DEFAULT_DISARM): cv.string,
            }
        ),
        _state_validator,
    )
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the manual MQTT alarm platform."""
    # Make sure MQTT integration is enabled and the client is available
    # We cannot count on dependencies as the alarm_control_panel platform setup
    # also will be triggered when mqtt is loading the `alarm_control_panel` platform
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return
    add_entities(
        [
            ManualMQTTAlarm(
                hass,
                config[CONF_NAME],
                config.get(CONF_CODE),
                config.get(CONF_CODE_TEMPLATE),
                config.get(CONF_DISARM_AFTER_TRIGGER, DEFAULT_DISARM_AFTER_TRIGGER),
                config.get(mqtt.CONF_STATE_TOPIC),
                config.get(mqtt.CONF_COMMAND_TOPIC),
                config.get(mqtt.CONF_QOS),
                config.get(CONF_CODE_ARM_REQUIRED),
                config.get(CONF_PAYLOAD_DISARM),
                config.get(CONF_PAYLOAD_ARM_HOME),
                config.get(CONF_PAYLOAD_ARM_AWAY),
                config.get(CONF_PAYLOAD_ARM_NIGHT),
                config.get(CONF_PAYLOAD_ARM_VACATION),
                config.get(CONF_PAYLOAD_ARM_CUSTOM_BYPASS),
                config,
            )
        ]
    )


class ManualMQTTAlarm(AlarmControlPanelEntity):
    """Representation of an alarm status.

    When armed, will be pending for 'pending_time', after that armed.
    When triggered, will be pending for the triggering state's 'delay_time'
    plus the triggered state's 'pending_time'.
    After that will be triggered for 'trigger_time', after that we return to
    the previous state or disarm if `disarm_after_trigger` is true.
    A trigger_time of zero disables the alarm_trigger service.
    """

    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.ARM_VACATION
        | AlarmControlPanelEntityFeature.TRIGGER
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )

    def __init__(
        self,
        hass,
        name,
        code,
        code_template,
        disarm_after_trigger,
        state_topic,
        command_topic,
        qos,
        code_arm_required,
        payload_disarm,
        payload_arm_home,
        payload_arm_away,
        payload_arm_night,
        payload_arm_vacation,
        payload_arm_custom_bypass,
        config,
    ):
        """Init the manual MQTT alarm panel."""
        self._state = AlarmControlPanelState.DISARMED
        self._hass = hass
        self._attr_name = name
        if code_template:
            self._code = code_template
        else:
            self._code = code or None
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
        self._pending_time_by_state = {
            state: config[state][CONF_PENDING_TIME]
            for state in SUPPORTED_PENDING_STATES
        }

        self._state_topic = state_topic
        self._command_topic = command_topic
        self._qos = qos
        self._attr_code_arm_required = code_arm_required
        self._payload_disarm = payload_disarm
        self._payload_arm_home = payload_arm_home
        self._payload_arm_away = payload_arm_away
        self._payload_arm_night = payload_arm_night
        self._payload_arm_vacation = payload_arm_vacation
        self._payload_arm_custom_bypass = payload_arm_custom_bypass

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of the device."""
        if self._state == AlarmControlPanelState.TRIGGERED:
            if self._within_pending_time(self._state):
                return AlarmControlPanelState.PENDING
            trigger_time = self._trigger_time_by_state[self._previous_state]
            if (
                self._state_ts + self._pending_time(self._state) + trigger_time
            ) < dt_util.utcnow():
                if self._disarm_after_trigger:
                    return AlarmControlPanelState.DISARMED
                self._state = self._previous_state
                return self._state

        if self._state in SUPPORTED_PENDING_STATES and self._within_pending_time(
            self._state
        ):
            return AlarmControlPanelState.PENDING

        return self._state

    @property
    def _active_state(self):
        """Get the current state."""
        if self.state == AlarmControlPanelState.PENDING:
            return self._previous_state
        return self._state

    def _pending_time(self, state):
        """Get the pending time."""
        pending_time = self._pending_time_by_state[state]
        if state == AlarmControlPanelState.TRIGGERED:
            pending_time += self._delay_time_by_state[self._previous_state]
        return pending_time

    def _within_pending_time(self, state):
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
        self._async_validate_code(code, AlarmControlPanelState.DISARMED)
        self._state = AlarmControlPanelState.DISARMED
        self._state_ts = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._async_validate_code(code, AlarmControlPanelState.ARMED_HOME)
        self._async_update_state(AlarmControlPanelState.ARMED_HOME)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._async_validate_code(code, AlarmControlPanelState.ARMED_AWAY)
        self._async_update_state(AlarmControlPanelState.ARMED_AWAY)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        self._async_validate_code(code, AlarmControlPanelState.ARMED_NIGHT)
        self._async_update_state(AlarmControlPanelState.ARMED_NIGHT)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        self._async_validate_code(code, AlarmControlPanelState.ARMED_VACATION)
        self._async_update_state(AlarmControlPanelState.ARMED_VACATION)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command."""
        self._async_validate_code(code, AlarmControlPanelState.ARMED_CUSTOM_BYPASS)
        self._async_update_state(AlarmControlPanelState.ARMED_CUSTOM_BYPASS)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command.

        No code needed, a trigger time of zero for the current state
        disables the alarm.
        """
        if not self._trigger_time_by_state[self._active_state]:
            return
        self._async_update_state(AlarmControlPanelState.TRIGGERED)

    def _async_update_state(self, state: str) -> None:
        """Update the state."""
        if self._state == state:
            return

        self._previous_state = self._state
        self._state = state
        self._state_ts = dt_util.utcnow()
        self.async_write_ha_state()

        pending_time = self._pending_time(state)
        if state == AlarmControlPanelState.TRIGGERED:
            async_track_point_in_time(
                self._hass, self.async_scheduled_update, self._state_ts + pending_time
            )

            trigger_time = self._trigger_time_by_state[self._previous_state]
            async_track_point_in_time(
                self._hass,
                self.async_scheduled_update,
                self._state_ts + pending_time + trigger_time,
            )
        elif state in SUPPORTED_PENDING_STATES and pending_time:
            async_track_point_in_time(
                self._hass, self.async_scheduled_update, self._state_ts + pending_time
            )

    def _async_validate_code(self, code, state):
        """Validate given code."""
        if (
            state != AlarmControlPanelState.DISARMED and not self.code_arm_required
        ) or self._code is None:
            return

        if isinstance(self._code, str):
            alarm_code = self._code
        else:
            alarm_code = self._code.async_render(
                from_state=self._state, to_state=state, parse_result=False
            )

        if not alarm_code or code == alarm_code:
            return

        raise HomeAssistantError("Invalid alarm code provided")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.state != AlarmControlPanelState.PENDING:
            return {}
        return {
            ATTR_PRE_PENDING_STATE: self._previous_state,
            ATTR_POST_PENDING_STATE: self._state,
        }

    @callback
    def async_scheduled_update(self, now):
        """Update state at a scheduled point in time."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        async_track_state_change_event(
            self.hass, [self.entity_id], self._async_state_changed_listener
        )

        async def message_received(msg):
            """Run when new MQTT message has been received."""
            if msg.payload == self._payload_disarm:
                await self.async_alarm_disarm(self._code)
            elif msg.payload == self._payload_arm_home:
                await self.async_alarm_arm_home(self._code)
            elif msg.payload == self._payload_arm_away:
                await self.async_alarm_arm_away(self._code)
            elif msg.payload == self._payload_arm_night:
                await self.async_alarm_arm_night(self._code)
            elif msg.payload == self._payload_arm_vacation:
                await self.async_alarm_arm_vacation(self._code)
            elif msg.payload == self._payload_arm_custom_bypass:
                await self.async_alarm_arm_custom_bypass(self._code)
            else:
                _LOGGER.warning("Received unexpected payload: %s", msg.payload)
                return

        await mqtt.async_subscribe(
            self.hass, self._command_topic, message_received, self._qos
        )

    async def _async_state_changed_listener(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Publish state change to MQTT."""
        if (new_state := event.data["new_state"]) is None:
            return
        await mqtt.async_publish(
            self.hass, self._state_topic, new_state.state, self._qos, True
        )
