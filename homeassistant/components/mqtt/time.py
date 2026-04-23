"""Support for MQTT time platform."""

from __future__ import annotations

from collections.abc import Callable
import datetime
import logging
from typing import Any

from dateutil.parser import ParserError, parse
import voluptuous as vol

from homeassistant.components import time
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_STATE_TOPIC,
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

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DEFAULT_NAME = "MQTT Time"

MQTT_TIME_ATTRIBUTES_BLOCKED: frozenset[str] = frozenset()


PLATFORM_SCHEMA_MODERN = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT time through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttTimeEntity,
        time.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttTimeEntity(MqttEntity, TimeEntity):
    """Representation of the MQTT time entity."""

    _attr_native_value: datetime.time | None = None
    _attributes_extra_blocked = MQTT_TIME_ATTRIBUTES_BLOCKED
    _default_name = DEFAULT_NAME
    _entity_id_format = time.ENTITY_ID_FORMAT

    _optimistic: bool
    _command_template: Callable[
        [PublishPayloadType, dict[str, Any]], PublishPayloadType
    ]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
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
        if payload == PAYLOAD_NONE:
            self._attr_native_value = None
            return
        if payload == "":
            _LOGGER.debug(
                "Ignoring empty state payload on topic %s for entity %s",
                msg.topic,
                self.entity_id,
            )
            return
        try:
            value = parse(payload)
        except ParserError:
            _LOGGER.warning(
                "Invalid received time expression on topic %s for entity %s, got %s",
                msg.topic,
                self.entity_id,
                msg.payload,
            )
        else:
            self._attr_native_value = value.time()

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

    async def async_set_value(self, value: datetime.time) -> None:
        """Change the time."""
        payload = self._command_template(value.isoformat(), {"value": value})
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)
        if self._optimistic:
            self._attr_native_value = value
            self.async_write_ha_state()
