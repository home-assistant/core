"""Control a LocknAlert MQTT Alarm."""

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
    ALARM_CONTROL_PANEL_SUPPORTED_FEATURES,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_CODE_TRIGGER_REQUIRED,
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_PAYLOAD_ARM_AWAY,
    CONF_PAYLOAD_ARM_CUSTOM_BYPASS,
    CONF_PAYLOAD_ARM_HOME,
    CONF_PAYLOAD_ARM_NIGHT,
    CONF_PAYLOAD_ARM_VACATION,
    CONF_PAYLOAD_DISARM,
    CONF_PAYLOAD_TRIGGER,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_SUPPORTED_FEATURES,
    DEFAULT_ALARM_CONTROL_PANEL_COMMAND_TEMPLATE,
    DEFAULT_PAYLOAD_ARM_AWAY,
    DEFAULT_PAYLOAD_ARM_CUSTOM_BYPASS,
    DEFAULT_PAYLOAD_ARM_HOME,
    DEFAULT_PAYLOAD_ARM_NIGHT,
    DEFAULT_PAYLOAD_ARM_VACATION,
    DEFAULT_PAYLOAD_DISARM,
    DEFAULT_PAYLOAD_TRIGGER,
    PAYLOAD_NONE,
    REMOTE_CODE,
    REMOTE_CODE_TEXT,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .templates import MqttCommandTemplate, MqttValueTemplate
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

MQTT_ALARM_ATTRIBUTES_BLOCKED = frozenset(
    {
        alarm.ATTR_CHANGED_BY,
        alarm.ATTR_CODE_ARM_REQUIRED,
        alarm.ATTR_CODE_FORMAT,
    }
)

DEFAULT_NAME = "LocknAlert MQTT Alarm"

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(
            CONF_SUPPORTED_FEATURES,
            default=list(ALARM_CONTROL_PANEL_SUPPORTED_FEATURES),
        ): [vol.In(ALARM_CONTROL_PANEL_SUPPORTED_FEATURES)],
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_DISARM_REQUIRED, default=True): cv.boolean,
        vol.Optional(CONF_CODE_TRIGGER_REQUIRED, default=True): cv.boolean,
        vol.Optional(
            CONF_COMMAND_TEMPLATE, default=DEFAULT_ALARM_CONTROL_PANEL_COMMAND_TEMPLATE
        ): cv.template,
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(
            CONF_PAYLOAD_ARM_AWAY, default=DEFAULT_PAYLOAD_ARM_AWAY
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_ARM_HOME, default=DEFAULT_PAYLOAD_ARM_HOME
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_ARM_NIGHT, default=DEFAULT_PAYLOAD_ARM_NIGHT
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_ARM_VACATION, default=DEFAULT_PAYLOAD_ARM_VACATION
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_ARM_CUSTOM_BYPASS, default=DEFAULT_PAYLOAD_ARM_CUSTOM_BYPASS
        ): cv.string,
        vol.Optional(CONF_PAYLOAD_DISARM, default=DEFAULT_PAYLOAD_DISARM): cv.string,
        vol.Optional(CONF_PAYLOAD_TRIGGER, default=DEFAULT_PAYLOAD_TRIGGER): cv.string,
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
    """Set up LocknAlert MQTT alarm control panel entities for a config entry.

    Delegates to :func:`~.entity.async_setup_entity_entry_helper` which
    registers discovery and YAML-based entity creation.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The locknalert_mqtt config entry.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback used to
            register newly discovered or configured entities with HA.
    """
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        LocknAlertMqttAlarm,
        alarm.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class LocknAlertMqttAlarm(MqttEntity, alarm.AlarmControlPanelEntity):
    """HA alarm control panel entity that bridges a LocknAlert MQTT alarm panel.

    Subscribes to the configured state topic to receive alarm state updates and
    publishes command payloads rendered through the command template to the
    command topic when an arm/disarm/trigger action is invoked.
    """

    _default_name = DEFAULT_NAME
    _entity_id_format = alarm.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_ALARM_ATTRIBUTES_BLOCKED

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the discovery schema used to validate this entity's config.

        Returns:
            vol.Schema: The voluptuous schema for alarm control panel discovery.
        """
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """Apply a (new) config dict to the entity, wiring up templates and features.

        Args:
            config (ConfigType): Validated configuration dictionary for this entity.
        """
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value
        self._command_template = MqttCommandTemplate(
            config[CONF_COMMAND_TEMPLATE], entity=self
        ).async_render

        self._attr_supported_features = AlarmControlPanelEntityFeature(0)
        for feature in self._config[CONF_SUPPORTED_FEATURES]:
            self._attr_supported_features |= ALARM_CONTROL_PANEL_SUPPORTED_FEATURES[
                feature
            ]

        if (code := self._config.get(CONF_CODE)) is None:
            self._attr_code_format = None
        elif code == REMOTE_CODE or str(code).isdigit():
            self._attr_code_format = alarm.CodeFormat.NUMBER
        else:
            self._attr_code_format = alarm.CodeFormat.TEXT
        self._attr_code_arm_required = bool(self._config[CONF_CODE_ARM_REQUIRED])

    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle an incoming state MQTT message and update alarm state.

        Renders the payload through the value template, validates it against the
        known AlarmControlPanelState values, and writes the result to
        ``_attr_alarm_state``.  Unexpected or empty payloads are logged and
        discarded.

        Args:
            msg (ReceiveMessage): The received MQTT message containing topic and payload.
        """
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
        self._attr_alarm_state = AlarmControlPanelState(str(payload))

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """Register topic subscriptions, replacing any previously registered ones."""
        self.add_subscription(
            CONF_STATE_TOPIC, self._state_message_received, {"_attr_alarm_state"}
        )

    async def _subscribe_topics(self) -> None:
        """Activate the prepared topic subscriptions with the MQTT broker."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send the disarm command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied disarm code, or ``None`` if not provided.
        """
        code_required: bool = self._config[CONF_CODE_DISARM_REQUIRED]
        if code_required and not self._validate_code(code, "disarming"):
            return
        payload: str = self._config[CONF_PAYLOAD_DISARM]
        await self._publish(code, payload)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send the arm-home command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied arm code, or ``None`` if not
                provided.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming home"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_HOME]
        await self._publish(code, action)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send the arm-away command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied arm code, or ``None`` if not
                provided.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming away"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_AWAY]
        await self._publish(code, action)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send the arm-night command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied arm code, or ``None`` if not
                provided.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming night"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_NIGHT]
        await self._publish(code, action)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send the arm-vacation command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied arm code, or ``None`` if not
                provided.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming vacation"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_VACATION]
        await self._publish(code, action)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send the arm-custom-bypass command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied arm code, or ``None`` if not
                provided.
        """
        code_required: bool = self._config[CONF_CODE_ARM_REQUIRED]
        if code_required and not self._validate_code(code, "arming custom bypass"):
            return
        action: str = self._config[CONF_PAYLOAD_ARM_CUSTOM_BYPASS]
        await self._publish(code, action)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send the trigger command to the alarm via MQTT.

        Args:
            code (str | None): User-supplied trigger code, or ``None`` if not
                provided.
        """
        code_required: bool = self._config[CONF_CODE_TRIGGER_REQUIRED]
        if code_required and not self._validate_code(code, "triggering"):
            return
        action: str = self._config[CONF_PAYLOAD_TRIGGER]
        await self._publish(code, action)

    async def _publish(self, code: str | None, action: str) -> None:
        """Render the command template and publish the result to the command topic.

        Args:
            code (str | None): The user-supplied code, passed as the
                ``code`` variable into the command template.
            action (str): The alarm action payload (e.g. ``"ARM_AWAY"``),
                passed as the ``action`` variable into the command template.
        """
        variables = {"action": action, "code": code}
        payload = self._command_template(None, variables=variables)
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)

    def _validate_code(self, code: str | None, state: str) -> bool:
        """Return True if *code* satisfies the configured code requirement.

        Validation passes when no code is configured, when *code* exactly
        matches the configured code, or when the configured code is one of the
        remote-code sentinels (``REMOTE_CODE`` or ``REMOTE_CODE_TEXT``) and
        a non-empty *code* was supplied.  Failures are logged as warnings.

        Args:
            code (str | None): The code supplied by the user, or ``None``.
            state (str): Human-readable action description used in the warning
                log (e.g. ``"disarming"``, ``"arming away"``).

        Returns:
            bool: ``True`` if the code is valid, ``False`` otherwise.
        """
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
