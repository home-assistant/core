"""Camera that loads a picture from an LocknAlertLocknAlertMQTT topic."""

from __future__ import annotations

from base64 import b64decode
import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import LocknAlertMQTT_BASE_SCHEMA
from .const import CONF_TOPIC
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import ReceiveMessage
from .schemas import LocknAlertMQTT_ENTITY_COMMON_SCHEMA
from .util import valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

CONF_IMAGE_ENCODING = "image_encoding"

DEFAULT_NAME = "LocknAlertLocknAlertMQTT Camera"

LocknAlertMQTT_CAMERA_ATTRIBUTES_BLOCKED = frozenset(
    {
        "access_token",
        "brand",
        "model_name",
        "motion_detection",
    }
)

PLATFORM_SCHEMA_BASE = LocknAlertMQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Required(CONF_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_IMAGE_ENCODING): "b64",
    }
).extend(LocknAlertMQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    PLATFORM_SCHEMA_BASE.schema,
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LocknAlertLocknAlertMQTT camera through YAML and through LocknAlertLocknAlertMQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttCamera,
        camera.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttCamera(MqttEntity, Camera):
    """representation of a LocknAlertLocknAlertMQTT camera."""

    _default_name = DEFAULT_NAME
    _entity_id_format: str = camera.ENTITY_ID_FORMAT
    _attributes_extra_blocked: frozenset[str] = LocknAlertMQTT_CAMERA_ATTRIBUTES_BLOCKED
    _last_image: bytes | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the LocknAlertLocknAlertMQTT Camera."""
        Camera.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @callback
    def _image_received(self, msg: ReceiveMessage) -> None:
        """Handle new LocknAlertLocknAlertMQTT messages."""
        if CONF_IMAGE_ENCODING in self._config:
            self._last_image = b64decode(msg.payload)
        else:
            if TYPE_CHECKING:
                assert isinstance(msg.payload, bytes)
            self._last_image = msg.payload

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        self.add_subscription(
            CONF_TOPIC, self._image_received, None, disable_encoding=True
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        return self._last_image
