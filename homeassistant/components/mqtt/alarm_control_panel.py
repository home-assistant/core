"""Control a MQTT alarm."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_SUPPORTED_FEATURES,
    PAYLOAD_NONE,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import MqttCommandTemplate, MqttValueTemplate, ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_SUPPORTED_FEATURES = {
    "arm_home": AlarmControlPanelEntityFeature.ARM_HOME,
    "arm_away": AlarmControlPanelEntityFeature.ARM_AWAY,
    "arm_night": AlarmControlPanelEntityFeature.ARM_NIGHT,
    "arm_vacation": AlarmControlPanelEntityFeature.ARM_VACATION,
    "arm_custom_bypass": AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS,
    "trigger": AlarmControlPanelEntityFeature.TRIGGER,
}

CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_DISARM_REQUIRED = "code_disarm_required"
CONF_CODE_TRIGGER_REQUIRED = "code_trigger_required"
CONF_PAYLOAD_DISARM = "payload_disarm"
CONF_PAYLOAD_ARM_HOME = "payload_arm_home"
CONF_PAYLOAD_ARM_AWAY = "payload_arm_away"
CONF_PAYLOAD_ARM_NIGHT = "payload_arm_night"
CONF_PAYLOAD_ARM_VACATION = "payload_arm_vacation"
CONF_PAYLOAD_ARM_CUSTOM_BYPASS = "payload_arm_custom_bypass"
CONF_PAYLOAD_TRIGGER = "payload_trigger"

MQTT_ALARM_ATTRIBUTES_BLOCKED = frozenset(
    {
        alarm.ATTR_CHANGED_BY,
        alarm.ATTR_CODE_ARM_REQUIRED,
        alarm.ATTR_CODE_FORMAT,
    }
)

DEFAULT_COMMAND_TEMPLATE = "{{action}}"
DEFAULT_ARM_NIGHT = "ARM_NIGHT"
DEFAULT_ARM_VACATION = "ARM_VACATION"
DEFAULT_ARM_AWAY = "ARM_AWAY"
DEFAULT_ARM_HOME = "ARM_HOME"
DEFAULT_ARM_CUSTOM_BYPASS = "ARM_CUSTOM_BYPASS"
DEFAULT_DISARM = "DISARM"
DEFAULT_TRIGGER = "TRIGGER"
DEFAULT_NAME = "MQTT Alarm"

REMOTE_CODE = "REMOTE_CODE"
REMOTE_CODE_TEXT = "REMOTE_CODE_TEXT"

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_SUPPORTED_FEATURES, default=list(_SUPPORTED_FEATURES)): [
            vol.In(_SUPPORTED_FEATURES)
        ],
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_DISARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_TRIGGER_REQUIRED, default=True): cv.boolean,
        vol.Optional(
            CONF_COMMAND_TEMPLATE, default=DEFAULT_COMMAND_TEMPLATE
        ): cv.template,
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_PAYLOAD_ARM_AWAY, default=DEFAULT_ARM_AWAY): cv.string,
        vol.Optional(CONF_PAYLOAD_ARM_HOME, default=DEFAULT_ARM_HOME): cv.string,
        vol.Optional(CONF_PAYLOAD_ARM_NIGHT, default=DEFAULT_ARM_NIGHT): cv.string,
        vol.Optional(
            CONF_PAYLOAD_ARM_VACATION, default=DEFAULT_ARM_VACATION
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_ARM_CUSTOM_BYPASS, default=DEFAULT_ARM_CUSTOM_BYPASS
        ): cv.string,
        vol.Optional(CONF_PAYLOAD_DISARM, default=DEFAULT_DISARM): cv.string,
        vol.Optional(CONF_PAYLOAD_TRIGGER, default=DEFAULT_TRIGGER): cv.string,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Required(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT alarm control panel through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttAlarm,
        alarm.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttAlarm(MqttEntity, alarm.AlarmControlPanelEntity):
    """Representation of a MQTT alarm status."""

    _default_name = DEFAULT_NAME
    _entity_id_format = alarm.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_ALARM_ATTRIBUTES_BLOCKED

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value
        self._command_template = MqttCommandTemplate(
            config[CONF_COMMAND_TEMPLATE], entity=self
        ).async_render

        for feature in self._config[CONF_SUPPORTED_FEATURES]:
            self._attr_supported_features |= _SUPPORTED_FEATURES[feature]

        if (code := self._config.get(CONF_CODE)) is None:
            self._attr_code_format = None
        elif code == REMOTE_CODE or str(code).isdigit():
            self._attr_code_format = alarm.CodeFormat.NUMBER
        else:
            self._attr_code_format = alarm.CodeFormat.TEXT
        self._attr_code_arm_required = bool(self._config[CONF_CODE_ARM_REQUIRED])

    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Run when new MQTT message has been received."""
        payload = self._value_template(msg.payload)
        if not payload.strip():  # No output from template, ignore
            _LOGGER.debug(
                "Ignoring empty payload '%s' after rendering for topic %s",
                payload,
                msg.topic,
            )
            return
        if payload == PAYLOAD_NONE:
            self._attr_alarm_state = None
            return
        if payload not in (
            AlarmControlPanelState.DISARMED,
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_VACATION,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            AlarmControlPanelState.PENDING,
            AlarmControlPanelState.ARMING,
            AlarmControlPanelState.DISARMING,
            AlarmControlPanelState.TRIGGERED,
        ):
            _LOGGER.warning("Received unexpected payload: %s", msg.payload)
            return
        assert isinstance(payload, str)
        self._attr_alarm_state = AlarmControlPanelState(payload)

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC, self._state_message_received, {"_attr_alarm_state"}
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_DISARM_REQUIRED]
        if code_required and not self._validate_code(code, "disarming"):
            return
        payload: str = self._config[CONF_PAYLOAD_DISARM]
        await self._publish(code, payload)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming home"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_HOME]
        await self._publish(code, action)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming away"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_AWAY]
        await self._publish(code, action)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming night"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_NIGHT]
        await self._publish(code, action)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming vacation"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_VACATION]
        await self._publish(code, action)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming custom bypass"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_CUSTOM_BYPASS]
        await self._publish(code, action)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send trigger command.

        This method is a coroutine.
        """
        code_required: bool = self._config[CONF_CODE_TRIGGER_REQUIRED]
        if code_required and not self._validate_code(code, "triggering"):
            return
        action: str = self._config[CONF_PAYLOAD_TRIGGER]
        await self._publish(code, action)

    async def _publish(self, code: str | None, action: str) -> None:
        """Publish via mqtt."""
        variables = {"action": action, "code": code}
        payload = self._command_template(None, variables=variables)
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)

    def _validate_code(self, code: str | None, state: str) -> bool:
        """Validate given code."""
        conf_code: str | None = self._config.get(CONF_CODE)
        check = bool(
            conf_code is None
            or code == conf_code
            or (conf_code == REMOTE_CODE and code)
            or (conf_code == REMOTE_CODE_TEXT and code)
        )
        if not check:
            _LOGGER.warning("Wrong code entered for %s", state)
        return check
