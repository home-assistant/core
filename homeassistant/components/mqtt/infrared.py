"""Support for MQTT infrared platform."""

from collections.abc import Callable
import logging
from typing import Any, override

import orjson
import voluptuous as vol

from homeassistant.components import infrared
from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads_object

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_RETAIN,
    CONF_SCHEMA,
    CONF_STATE_TOPIC,
    DEFAULT_RETAIN,
    PAYLOAD_NONE,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_EMITTER_NAME = "MQTT Infrared emitter"
DEFAULT_RECEIVER_NAME = "MQTT Infrared receiver"

MQTT_INFRARED_ATTRIBUTES_BLOCKED: frozenset[str] = frozenset()

SIGNAL_SCHEMA = vol.Schema(
    {
        vol.Required("timings"): [int],
        vol.Required("modulation"): int,
    }
)


def validate_mqtt_infrared_config(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT infrared entity config schema."""
    schemas: dict[str, VolSchemaType] = {
        "emitter": EMITTER_SCHEMA,
        "receiver": RECEIVER_SCHEMA,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


def validate_mqtt_infrared_discovery(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT infrared entity discovery schema."""
    schemas: dict[str, VolSchemaType] = {
        "emitter": EMITTER_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA),
        "receiver": RECEIVER_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA),
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


INFRARED_BASE_SCHEMA = vol.Schema(
    {vol.Required(CONF_SCHEMA): vol.All(vol.Lower, vol.Any("emitter", "receiver"))},
    extra=vol.ALLOW_EXTRA,
)

EMITTER_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_SCHEMA): "emitter",
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

RECEIVER_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_SCHEMA): "receiver",
        vol.Required(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    INFRARED_BASE_SCHEMA,
    validate_mqtt_infrared_config,
)
DISCOVERY_SCHEMA = vol.All(
    INFRARED_BASE_SCHEMA,
    validate_mqtt_infrared_discovery,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT infrared device through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        None,
        infrared.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
        schema_class_mapping={
            "emitter": MqttInfraredEmitterEntity,
            "receiver": MqttInfraredReceiverEntity,
        },
    )


class MqttInfraredEmitterEntity(MqttEntity, InfraredEmitterEntity):
    """Representation of the MQTT infrared emitter entity."""

    _attributes_extra_blocked = MQTT_INFRARED_ATTRIBUTES_BLOCKED
    _default_name = DEFAULT_EMITTER_NAME
    _entity_id_format = infrared.ENTITY_ID_FORMAT

    _command_template: Callable[
        [PublishPayloadType, dict[str, Any]], PublishPayloadType
    ]

    @staticmethod
    @override
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @override
    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE),
            entity=self,
        ).async_render

    @callback
    @override
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    @override
    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    @override
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via MQTT."""

        command_vars: dict[str, Any] = {
            "timings": command.get_raw_timings(),
            "modulation": command.modulation,
            "repeat_count": command.repeat_count,
        }
        payload = self._command_template(
            orjson.dumps(command_vars).decode(), command_vars
        )
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)


class MqttInfraredReceiverEntity(MqttEntity, InfraredReceiverEntity):
    """Representation of the MQTT infrared receiver entity."""

    _attributes_extra_blocked = MQTT_INFRARED_ATTRIBUTES_BLOCKED
    _default_name = DEFAULT_RECEIVER_NAME
    _entity_id_format = infrared.ENTITY_ID_FORMAT

    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    @staticmethod
    @override
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @override
    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

    @callback
    def _handle_state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving state message via MQTT."""
        payload = self._value_template(msg.payload)
        if not payload or payload == PAYLOAD_NONE:
            _LOGGER.debug(
                "Ignoring payload for %s on topic %s, with template %s",
                self.entity_id,
                self._config[CONF_STATE_TOPIC],
                self._config.get(CONF_VALUE_TEMPLATE),
            )
            return
        try:
            payload_dict = SIGNAL_SCHEMA(json_loads_object(payload))
        except (*JSON_DECODE_EXCEPTIONS, vol.Invalid, TypeError):
            _LOGGER.warning(
                "Invalid message received for %s on topic %s, with template %s. "
                "Message is not a valid signal JSON message. Got %s",
                self.entity_id,
                self._config[CONF_STATE_TOPIC],
                self._config.get(CONF_VALUE_TEMPLATE),
                msg.payload,
            )
        else:
            self._handle_received_signal(
                InfraredReceivedSignal(
                    modulation=payload_dict["modulation"],
                    timings=payload_dict["timings"],
                )
            )

    @callback
    @override
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC,
            self._handle_state_message_received,
            None,
        )

    @override
    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)
