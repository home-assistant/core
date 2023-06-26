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
from .const import CONF_QOS
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import ReceiveMessage
from .util import get_mqtt_data, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_CONTENT_TYPE = "content_type"
CONF_IMAGE_ENCODING = "image_encoding"
CONF_IMAGE_TOPIC = "image_topic"

DEFAULT_NAME = "MQTT Image"


PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_CONTENT_TYPE, default=DEFAULT_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_IMAGE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_IMAGE_ENCODING): "b64",
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


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
        ImageEntity.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._topic = {key: config.get(key) for key in (CONF_IMAGE_TOPIC,)}
        self._attr_content_type = config[CONF_CONTENT_TYPE]

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        topics: dict[str, Any] = {}

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

        topics[self._config[CONF_IMAGE_TOPIC]] = {
            "topic": self._config[CONF_IMAGE_TOPIC],
            "msg_callback": image_data_received,
            "qos": self._config[CONF_QOS],
            "encoding": None,
        }

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._last_image
