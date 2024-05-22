"""Support for MQTT events."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import event
from homeassistant.components.event import (
    ENTITY_ID_FORMAT,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads_object

from . import subscription
from .config import MQTT_RO_SCHEMA
from .const import (
    CONF_ENCODING,
    CONF_QOS,
    CONF_STATE_TOPIC,
    PAYLOAD_EMPTY_JSON,
    PAYLOAD_NONE,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entity_entry_helper,
)
from .models import (
    DATA_MQTT,
    MqttValueTemplate,
    MqttValueTemplateException,
    PayloadSentinel,
    ReceiveMessage,
    ReceivePayloadType,
)

_LOGGER = logging.getLogger(__name__)

CONF_EVENT_TYPES = "event_types"

MQTT_EVENT_ATTRIBUTES_BLOCKED = frozenset(
    {
        event.ATTR_EVENT_TYPE,
        event.ATTR_EVENT_TYPES,
    }
)

DEFAULT_NAME = "MQTT Event"
DEFAULT_FORCE_UPDATE = False
DEVICE_CLASS_SCHEMA = vol.All(vol.Lower, vol.Coerce(EventDeviceClass))

_PLATFORM_SCHEMA_BASE = MQTT_RO_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASS_SCHEMA,
        vol.Optional(CONF_NAME): vol.Any(None, cv.string),
        vol.Required(CONF_EVENT_TYPES): vol.All(cv.ensure_list, [cv.string]),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    _PLATFORM_SCHEMA_BASE,
)

DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT event through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttEvent,
        event.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttEvent(MqttEntity, EventEntity):
    """Representation of an event that can be updated using MQTT."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_EVENT_ATTRIBUTES_BLOCKED
    _template: Callable[[ReceivePayloadType, PayloadSentinel], ReceivePayloadType]

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_event_types = config[CONF_EVENT_TYPES]
        self._template = MqttValueTemplate(
            self._config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, dict[str, Any]] = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            if msg.retain:
                _LOGGER.debug(
                    "Ignoring event trigger from replayed retained payload '%s' on topic %s",
                    msg.payload,
                    msg.topic,
                )
                return
            event_attributes: dict[str, Any] = {}
            event_type: str
            try:
                payload = self._template(msg.payload, PayloadSentinel.DEFAULT)
            except MqttValueTemplateException as exc:
                _LOGGER.warning(exc)
                return
            if (
                not payload
                or payload is PayloadSentinel.DEFAULT
                or payload in (PAYLOAD_NONE, PAYLOAD_EMPTY_JSON)
            ):
                _LOGGER.debug(
                    "Ignoring empty payload '%s' after rendering for topic %s",
                    payload,
                    msg.topic,
                )
                return
            try:
                event_attributes = json_loads_object(payload)
                event_type = str(event_attributes.pop(event.ATTR_EVENT_TYPE))
                _LOGGER.debug(
                    (
                        "JSON event data detected after processing payload '%s' on"
                        " topic %s, type %s, attributes %s"
                    ),
                    payload,
                    msg.topic,
                    event_type,
                    event_attributes,
                )
            except KeyError:
                _LOGGER.warning(
                    (
                        "`event_type` missing in JSON event payload, "
                        " '%s' on topic %s"
                    ),
                    payload,
                    msg.topic,
                )
                return
            except JSON_DECODE_EXCEPTIONS:
                _LOGGER.warning(
                    (
                        "No valid JSON event payload detected, "
                        "value after processing payload"
                        " '%s' on topic %s"
                    ),
                    payload,
                    msg.topic,
                )
                return
            try:
                self._trigger_event(event_type, event_attributes)
            except ValueError:
                _LOGGER.warning(
                    "Invalid event type %s for %s received on topic %s, payload %s",
                    event_type,
                    self.entity_id,
                    msg.topic,
                    payload,
                )
                return
            mqtt_data = self.hass.data[DATA_MQTT]
            mqtt_data.state_write_requests.write_state_request(self)

        topics["state_topic"] = {
            "topic": self._config[CONF_STATE_TOPIC],
            "msg_callback": message_received,
            "qos": self._config[CONF_QOS],
            "encoding": self._config[CONF_ENCODING] or None,
        }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)
