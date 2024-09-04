"""Support for MQTT text platform."""

from __future__ import annotations

from collections.abc import Callable
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import text
from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_VALUE_TEMPLATE,
    MAX_LENGTH_STATE_STATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import CONF_COMMAND_TEMPLATE, CONF_COMMAND_TOPIC, CONF_STATE_TOPIC
from .mixins import MqttEntity, async_setup_entity_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import check_state_too_long

_LOGGER = logging.getLogger(__name__)

CONF_MAX = "max"
CONF_MIN = "min"
CONF_PATTERN = "pattern"

DEFAULT_NAME = "MQTT Text"
DEFAULT_PAYLOAD_RESET = "None"

MQTT_TEXT_ATTRIBUTES_BLOCKED = frozenset(
    {
        text.ATTR_MAX,
        text.ATTR_MIN,
        text.ATTR_MODE,
        text.ATTR_PATTERN,
    }
)


def valid_text_size_configuration(config: ConfigType) -> ConfigType:
    """Validate that the text length configuration is valid, throws if it isn't."""
    if config[CONF_MIN] > config[CONF_MAX]:
        raise vol.Invalid("text length min must be <= max")
    if config[CONF_MAX] > MAX_LENGTH_STATE_STATE:
        raise vol.Invalid(f"max text length must be <= {MAX_LENGTH_STATE_STATE}")

    return config


_PLATFORM_SCHEMA_BASE = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_MAX, default=MAX_LENGTH_STATE_STATE): cv.positive_int,
        vol.Optional(CONF_MIN, default=0): cv.positive_int,
        vol.Optional(CONF_MODE, default=text.TextMode.TEXT): vol.In(
            [text.TextMode.TEXT, text.TextMode.PASSWORD]
        ),
        vol.Optional(CONF_PATTERN): cv.is_regex,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    valid_text_size_configuration,
)

PLATFORM_SCHEMA_MODERN = vol.All(_PLATFORM_SCHEMA_BASE, valid_text_size_configuration)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT text through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttTextEntity,
        text.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttTextEntity(MqttEntity, TextEntity):
    """Representation of the MQTT text entity."""

    _attr_native_value: str | None = None
    _attributes_extra_blocked = MQTT_TEXT_ATTRIBUTES_BLOCKED
    _default_name = DEFAULT_NAME
    _entity_id_format = text.ENTITY_ID_FORMAT

    _compiled_pattern: re.Pattern[Any] | None
    _optimistic: bool
    _command_template: Callable[[PublishPayloadType], PublishPayloadType]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_native_max = config[CONF_MAX]
        self._attr_native_min = config[CONF_MIN]
        self._attr_mode = config[CONF_MODE]
        self._compiled_pattern = config.get(CONF_PATTERN)
        self._attr_pattern = (
            self._compiled_pattern.pattern if self._compiled_pattern else None
        )

        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE),
            entity=self,
        ).async_render
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value
        optimistic: bool = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or config.get(CONF_STATE_TOPIC) is None
        self._attr_assumed_state = bool(self._optimistic)

    @callback
    def _handle_state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving state message via MQTT."""
        payload = str(self._value_template(msg.payload))
        if check_state_too_long(_LOGGER, payload, self.entity_id, msg):
            return
        self._attr_native_value = payload

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC,
            self._handle_state_message_received,
            {"_attr_native_value"},
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_set_value(self, value: str) -> None:
        """Change the text."""
        payload = self._command_template(value)
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)
        if self._optimistic:
            self._attr_native_value = value
            self.async_write_ha_state()
