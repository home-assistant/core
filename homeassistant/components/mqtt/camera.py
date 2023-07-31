"""Camera that loads a picture from an MQTT topic."""
from __future__ import annotations

from base64 import b64decode
import functools
import logging

import voluptuous as vol

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import CONF_QOS, CONF_TOPIC
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import ReceiveMessage
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

CONF_IMAGE_ENCODING = "image_encoding"

DEFAULT_NAME = "MQTT Camera"

MQTT_CAMERA_ATTRIBUTES_BLOCKED = frozenset(
    {
        "access_token",
        "brand",
        "model_name",
        "motion_detection",
    }
)

PLATFORM_SCHEMA_BASE = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Required(CONF_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_IMAGE_ENCODING): "b64",
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    PLATFORM_SCHEMA_BASE.schema,
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT camera through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, camera.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT Camera."""
    async_add_entities([MqttCamera(hass, config, config_entry, discovery_data)])


class MqttCamera(MqttEntity, Camera):
    """representation of a MQTT camera."""

    _default_name = DEFAULT_NAME
    _entity_id_format: str = camera.ENTITY_ID_FORMAT
    _attributes_extra_blocked: frozenset[str] = MQTT_CAMERA_ATTRIBUTES_BLOCKED

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the MQTT Camera."""
        self._last_image: bytes | None = None

        Camera.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            if CONF_IMAGE_ENCODING in self._config:
                self._last_image = b64decode(msg.payload)
            else:
                assert isinstance(msg.payload, bytes)
                self._last_image = msg.payload

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_TOPIC],
                    "msg_callback": message_received,
                    "qos": self._config[CONF_QOS],
                    "encoding": None,
                }
            },
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        return self._last_image
