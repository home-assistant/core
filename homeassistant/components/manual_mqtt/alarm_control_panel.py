"""Support for manual alarms controllable via MQTT."""
import copy
import datetime
import json
import logging
import re

import voluptuous as vol

from homeassistant.components import mqtt
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
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
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    track_point_in_time,
)
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_CODE_TEMPLATE = "code_template"
CONF_CODE_ARM_REQUIRED = "code_arm_required"

CONF_PAYLOAD_DISARM = "payload_disarm"
CONF_PAYLOAD_ARM_HOME = "payload_arm_home"
CONF_PAYLOAD_ARM_AWAY = "payload_arm_away"
CONF_PAYLOAD_ARM_NIGHT = "payload_arm_night"
CONF_PAYLOAD_INVALID = "payload_invalid"
CONF_CONFIG_TOPIC = "config_topic"
CONF_STATUS_TOPIC = "status_topic"

DEFAULT_ALARM_NAME = "HA Alarm"
DEFAULT_DELAY_TIME = datetime.timedelta(seconds=60)
DEFAULT_ARMING_TIME = datetime.timedelta(seconds=60)
DEFAULT_TRIGGER_TIME = datetime.timedelta(seconds=120)
DEFAULT_DISARM_AFTER_TRIGGER = False
DEFAULT_ARM_AWAY = "ARM_AWAY"
DEFAULT_ARM_HOME = "ARM_HOME"
DEFAULT_ARM_NIGHT = "ARM_NIGHT"
DEFAULT_DISARM = "DISARM"
DEFAULT_INVALID = "INVALID"
DEFAULT_COMMAND_TOPIC = "home/alarm/set"
DEFAULT_CONFIG_TOPIC = "home/alarm/config"
DEFAULT_STATE_TOPIC = "home/alarm"
DEFAULT_STATUS_TOPIC = "home/alarm/status"

SUPPORTED_STATES = [
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
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
        mqtt.MQTT_BASE_PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_PLATFORM): "manual_mqtt",
                vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
                vol.Exclusive(CONF_CODE, "code validation"): cv.string,
                vol.Exclusive(CONF_CODE_TEMPLATE, "code validation"): cv.template,
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
                vol.Optional(STATE_ALARM_DISARMED, default={}): _state_schema(
                    STATE_ALARM_DISARMED
                ),
                vol.Optional(STATE_ALARM_TRIGGERED, default={}): _state_schema(
                    STATE_ALARM_TRIGGERED
                ),
                vol.Optional(
                    mqtt.CONF_COMMAND_TOPIC, default=DEFAULT_COMMAND_TOPIC
                ): mqtt.valid_publish_topic,
                vol.Optional(
                    CONF_CONFIG_TOPIC, default=DEFAULT_CONFIG_TOPIC
                ): mqtt.valid_publish_topic,
                vol.Optional(
                    CONF_STATUS_TOPIC, default=DEFAULT_STATUS_TOPIC
                ): mqtt.valid_publish_topic,
                vol.Optional(
                    mqtt.CONF_STATE_TOPIC, default=DEFAULT_STATE_TOPIC
                ): mqtt.valid_subscribe_topic,
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
                vol.Optional(CONF_PAYLOAD_DISARM, default=DEFAULT_DISARM): cv.string,
                vol.Optional(CONF_PAYLOAD_INVALID, default=DEFAULT_INVALID): cv.string,
            }
        ),
        _state_validator,
    )
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the manual MQTT alarm platform."""
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
                config.get(CONF_CONFIG_TOPIC),
                config.get(CONF_STATUS_TOPIC),
                config.get(mqtt.CONF_QOS),
                config.get(CONF_CODE_ARM_REQUIRED),
                config.get(CONF_PAYLOAD_DISARM),
                config.get(CONF_PAYLOAD_ARM_HOME),
                config.get(CONF_PAYLOAD_ARM_AWAY),
                config.get(CONF_PAYLOAD_ARM_NIGHT),
                config.get(CONF_PAYLOAD_INVALID),
                config,
            )
        ]
    )


class ManualMQTTAlarm(alarm.AlarmControlPanelEntity):
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
        disarm_after_trigger,
        state_topic,
        command_topic,
        config_topic,
        status_topic,
        qos,
        code_arm_required,
        payload_disarm,
        payload_arm_home,
        payload_arm_away,
        payload_arm_night,
        payload_invalid,
        config,
    ):
        """Init the manual MQTT alarm panel."""
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

        self._state_topic = state_topic
        self._command_topic = command_topic
        self._config_topic = config_topic
        self._status_topic = status_topic
        self._qos = qos
        self._payload_disarm = payload_disarm
        self._payload_arm_home = payload_arm_home
        self._payload_arm_away = payload_arm_away
        self._payload_arm_night = payload_arm_night
        self._payload_invalid = payload_invalid

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
                self._hass, self.async_update_ha_state, self._state_ts + pending_time
            )

            trigger_time = self._trigger_time_by_state[self._previous_state]
            track_point_in_time(
                self._hass,
                self.async_update_ha_state,
                self._state_ts + pending_time + trigger_time,
            )
        elif state in SUPPORTED_ARMING_STATES:
            arming_time = self._arming_time(state)
            if arming_time:
                track_point_in_time(
                    self._hass, self.async_update_ha_state, self._state_ts + arming_time
                )

    def _validate_code(self, code, state):
        """Validate given code."""
        if self._code is None:
            return True
        if isinstance(self._code, str):
            alarm_code = self._code
        else:
            alarm_code = self._code.render(from_state=self._state, to_state=state)
        check = not alarm_code or code == alarm_code
        if not check:
            _LOGGER.warning("Invalid code given for %s", state)
            mqtt.async_publish(
                self.hass, self._status_topic, self._payload_invalid, self._qos, False
            )

        return check

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.state != STATE_ALARM_PENDING and self.state != STATE_ALARM_ARMING:
            return {}
        return {
            ATTR_PREVIOUS_STATE: self._previous_state,
            ATTR_NEXT_STATE: self._state,
        }

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass & subscribe to MQTT Events."""
        await super().async_added_to_hass()

        async_track_state_change_event(
            self.hass, [self.entity_id], self._async_state_changed_listener
        )

        async def message_received(msg):
            """Run when new MQTT message has been received."""
            try:
                payload = json.loads(msg.payload)
                action = payload.get("action")
                code = payload.get("code")
            except ValueError:
                _LOGGER.error("Received non-JSON payload! That mode is deprecated.")
                action = msg.payload
                code = self._code
            if action == self._payload_disarm:
                await self.async_alarm_disarm(code)
            elif action == self._payload_arm_home:
                await self.async_alarm_arm_home(code)
            elif action == self._payload_arm_away:
                await self.async_alarm_arm_away(code)
            elif action == self._payload_arm_night:
                await self.async_alarm_arm_night(code)
            else:
                _LOGGER.warning("Received unexpected payload: %s", msg.payload)
                return

        await mqtt.async_subscribe(
            self.hass, self._command_topic, message_received, self._qos
        )

        config = {
            "version": 1,
            "code_arm_required": self._code_arm_required,
            "code_disarm_required": (self._code is not None),
            "state_topic": self._state_topic,
            "status_topic": self._status_topic,
            "command_topic": self._command_topic,
            "delay_times": self._delay_time_by_state,
            "arming_times": self._arming_time_by_state,
            "trigger_times": self._trigger_time_by_state,
        }

        def default(obj):
            if isinstance(obj, (datetime.timedelta)):
                return int(obj.total_seconds())
            return str(obj)

        mqtt.async_publish(
            self.hass,
            self._config_topic,
            json.dumps(config, default=default),
            self._qos,
            True,
        )

    async def _async_state_changed_listener(self, event):
        """Publish state change to MQTT."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        new_state_str = new_state.state
        if new_state_str == "arming":
            if new_state.attributes["next_state"] == "armed_away":
                new_state_str = "arming_away"
            elif new_state.attributes["next_state"] == "armed_home":
                new_state_str = "arming_home"
            elif new_state.attributes["next_state"] == "armed_night":
                new_state_str = "arming_night"
            else:
                _LOGGER.warning(
                    "Unknown arming next state: %s", new_state.attributes["next_state"]
                )
        mqtt.async_publish(self.hass, self._state_topic, new_state_str, self._qos, True)
