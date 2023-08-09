"""Support for MQTT images."""
from __future__ import annotations

from base64 import b64decode
import binascii
from collections.abc import Callable
import functools
import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.components import image
from homeassistant.components.image import (
    DEFAULT_CONTENT_TYPE,
    ImageEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import CONF_ENCODING, CONF_QOS
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import MessageCallbackType, MqttValueTemplate, ReceiveMessage
from .util import get_mqtt_data, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = "content_type"
CONF_IMAGE_ENCODING = "image_encoding"
CONF_IMAGE_TOPIC = "image_topic"
CONF_URL_TEMPLATE = "url_template"
CONF_URL_TOPIC = "url_topic"

DEFAULT_NAME = "MQTT Image"

GET_IMAGE_TIMEOUT = 10


def validate_topic_required(config: ConfigType) -> ConfigType:
    """Ensure at least one subscribe topic is configured."""
    if CONF_IMAGE_TOPIC not in config and CONF_URL_TOPIC not in config:
        raise vol.Invalid("Expected one of [`image_topic`, `url_topic`], got none")
    if CONF_CONTENT_TYPE in config and CONF_URL_TOPIC in config:
        raise vol.Invalid(
            "Option `content_type` can not be used together with `url_topic`"
        )
    return config


PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Exclusive(CONF_URL_TOPIC, "image_topic"): valid_subscribe_topic,
        vol.Exclusive(CONF_IMAGE_TOPIC, "image_topic"): valid_subscribe_topic,
        vol.Optional(CONF_IMAGE_ENCODING): "b64",
        vol.Optional(CONF_URL_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(PLATFORM_SCHEMA_BASE.schema, validate_topic_required)

DISCOVERY_SCHEMA = vol.All(
    PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA), validate_topic_required
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT image through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, image.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT Image."""
    async_add_entities([MqttImage(hass, config, config_entry, discovery_data)])


class MqttImage(MqttEntity, ImageEntity):
    """representation of a MQTT image."""

    _default_name = DEFAULT_NAME
    _entity_id_format: str = image.ENTITY_ID_FORMAT
    _last_image: bytes | None = None
    _client: httpx.AsyncClient
    _url_template: Callable[[ReceivePayloadType], ReceivePayloadType]
    _topic: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the MQTT Image."""
        self._client = get_async_client(hass)
        ImageEntity.__init__(self, hass)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._topic = {
            key: config.get(key)
            for key in (
                CONF_IMAGE_TOPIC,
                CONF_URL_TOPIC,
            )
        }
        if CONF_IMAGE_TOPIC in config:
            self._attr_content_type = config.get(
                CONF_CONTENT_TYPE, DEFAULT_CONTENT_TYPE
            )
        if CONF_URL_TOPIC in config:
            self._attr_image_url = None
        self._url_template = MqttValueTemplate(
            config.get(CONF_URL_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        topics: dict[str, Any] = {}

        def add_subscribe_topic(topic: str, msg_callback: MessageCallbackType) -> bool:
            """Add a topic to subscribe to."""
            encoding: str | None
            encoding = (
                None
                if CONF_IMAGE_TOPIC in self._config
                else self._config[CONF_ENCODING] or None
            )
            if has_topic := self._topic[topic] is not None:
                topics[topic] = {
                    "topic": self._topic[topic],
                    "msg_callback": msg_callback,
                    "qos": self._config[CONF_QOS],
                    "encoding": encoding,
                }
            return has_topic

        @callback
        @log_messages(self.hass, self.entity_id)
        def image_data_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            try:
                if CONF_IMAGE_ENCODING in self._config:
                    self._last_image = b64decode(msg.payload)
                else:
                    assert isinstance(msg.payload, bytes)
                    self._last_image = msg.payload
            except (binascii.Error, ValueError, AssertionError) as err:
                _LOGGER.error(
                    "Error processing image data received at topic %s: %s",
                    msg.topic,
                    err,
                )
                self._last_image = None
            self._attr_image_last_updated = dt_util.utcnow()
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_subscribe_topic(CONF_IMAGE_TOPIC, image_data_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def image_from_url_request_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""

            try:
                url = cv.url(self._url_template(msg.payload))
                self._attr_image_url = url
            except vol.Invalid:
                _LOGGER.error(
                    "Invalid image URL '%s' received at topic %s",
                    msg.payload,
                    msg.topic,
                )
            self._attr_image_last_updated = dt_util.utcnow()
            self._cached_image = None
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_subscribe_topic(CONF_URL_TOPIC, image_from_url_request_received)

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if CONF_IMAGE_TOPIC in self._config:
            return self._last_image
        return await super().async_image()
