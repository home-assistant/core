"""Configure update platform in a device through MQTT topic."""
from __future__ import annotations

from collections.abc import Callable
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import update
from homeassistant.components.update import (
    DEVICE_CLASSES_SCHEMA,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import JSON_DECODE_EXCEPTIONS, json_loads
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_RO_SCHEMA
from .const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    PAYLOAD_EMPTY_JSON,
)
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import MqttValueTemplate, ReceiveMessage
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Update"

CONF_ENTITY_PICTURE = "entity_picture"
CONF_LATEST_VERSION_TEMPLATE = "latest_version_template"
CONF_LATEST_VERSION_TOPIC = "latest_version_topic"
CONF_PAYLOAD_INSTALL = "payload_install"
CONF_RELEASE_SUMMARY = "release_summary"
CONF_RELEASE_URL = "release_url"
CONF_TITLE = "title"


PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_ENTITY_PICTURE): cv.string,
        vol.Optional(CONF_LATEST_VERSION_TEMPLATE): cv.template,
        vol.Optional(CONF_LATEST_VERSION_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_INSTALL): cv.string,
        vol.Optional(CONF_RELEASE_SUMMARY): cv.string,
        vol.Optional(CONF_RELEASE_URL): cv.string,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_TITLE): cv.string,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT update through configuration.yaml and dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, update.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT update."""
    async_add_entities([MqttUpdate(hass, config, config_entry, discovery_data)])


class MqttUpdate(MqttEntity, UpdateEntity, RestoreEntity):
    """Representation of the MQTT update entity."""

    _entity_id_format = update.ENTITY_ID_FORMAT

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None = None,
    ) -> None:
        """Initialize the MQTT update."""
        self._config = config
        self._attr_device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_release_summary = self._config.get(CONF_RELEASE_SUMMARY)
        self._attr_release_url = self._config.get(CONF_RELEASE_URL)
        self._attr_title = self._config.get(CONF_TITLE)
        self._entity_picture: str | None = self._config.get(CONF_ENTITY_PICTURE)

        UpdateEntity.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if self._entity_picture is not None:
            return self._entity_picture

        return super().entity_picture

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._templates = {
            CONF_VALUE_TEMPLATE: MqttValueTemplate(
                config.get(CONF_VALUE_TEMPLATE),
                entity=self,
            ).async_render_with_possible_json_value,
            CONF_LATEST_VERSION_TEMPLATE: MqttValueTemplate(
                config.get(CONF_LATEST_VERSION_TEMPLATE),
                entity=self,
            ).async_render_with_possible_json_value,
        }

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, Any] = {}

        def add_subscription(
            topics: dict[str, Any], topic: str, msg_callback: Callable
        ) -> None:
            if self._config.get(topic) is not None:
                topics[topic] = {
                    "topic": self._config[topic],
                    "msg_callback": msg_callback,
                    "qos": self._config[CONF_QOS],
                    "encoding": self._config[CONF_ENCODING] or None,
                }

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_state_message_received(msg: ReceiveMessage) -> None:
            """Handle receiving state message via MQTT."""
            payload = self._templates[CONF_VALUE_TEMPLATE](msg.payload)

            if not payload or payload == PAYLOAD_EMPTY_JSON:
                _LOGGER.debug(
                    "Ignoring empty payload '%s' after rendering for topic %s",
                    payload,
                    msg.topic,
                )
                return

            json_payload = {}
            try:
                json_payload = json_loads(payload)
                _LOGGER.debug(
                    "JSON payload detected after processing payload '%s' on topic %s",
                    json_payload,
                    msg.topic,
                )
            except JSON_DECODE_EXCEPTIONS:
                _LOGGER.debug(
                    "No valid (JSON) payload detected after processing payload '%s' on topic %s",
                    payload,
                    msg.topic,
                )
                json_payload["installed_version"] = payload

            if "installed_version" in json_payload:
                self._attr_installed_version = json_payload["installed_version"]
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

            if "latest_version" in json_payload:
                self._attr_latest_version = json_payload["latest_version"]
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

            if CONF_TITLE in json_payload and not self._attr_title:
                self._attr_title = json_payload[CONF_TITLE]
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

            if CONF_RELEASE_SUMMARY in json_payload and not self._attr_release_summary:
                self._attr_release_summary = json_payload[CONF_RELEASE_SUMMARY]
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

            if CONF_RELEASE_URL in json_payload and not self._attr_release_url:
                self._attr_release_url = json_payload[CONF_RELEASE_URL]
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

            if CONF_ENTITY_PICTURE in json_payload and not self._entity_picture:
                self._entity_picture = json_payload[CONF_ENTITY_PICTURE]
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_subscription(topics, CONF_STATE_TOPIC, handle_state_message_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_latest_version_received(msg: ReceiveMessage) -> None:
            """Handle receiving latest version via MQTT."""
            latest_version = self._templates[CONF_LATEST_VERSION_TEMPLATE](msg.payload)

            if isinstance(latest_version, str) and latest_version != "":
                self._attr_latest_version = latest_version
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_subscription(
            topics, CONF_LATEST_VERSION_TOPIC, handle_latest_version_received
        )

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Update the current value."""
        payload = self._config[CONF_PAYLOAD_INSTALL]

        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        support = 0

        if self._config.get(CONF_COMMAND_TOPIC) is not None:
            support |= UpdateEntityFeature.INSTALL

        return support
