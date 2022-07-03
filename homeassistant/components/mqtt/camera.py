"""Camera that loads a picture from an MQTT topic."""
from __future__ import annotations

from base64 import b64decode
import functools

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
from .const import CONF_ENCODING, CONF_QOS, CONF_TOPIC
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .util import valid_subscribe_topic

DEFAULT_NAME = "MQTT Camera"

MQTT_CAMERA_ATTRIBUTES_BLOCKED = frozenset(
    {
        "access_token",
        "brand",
        "model_name",
        "motion_detection",
    }
)

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_TOPIC): valid_subscribe_topic,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Camera under the camera platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_MODERN.schema),
    warn_for_legacy_schema(camera.DOMAIN),
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT camera configured under the camera platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        camera.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT camera through configuration.yaml and dynamically through MQTT discovery."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, camera.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, camera.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT Camera."""
    async_add_entities([MqttCamera(hass, config, config_entry, discovery_data)])


class MqttCamera(MqttEntity, Camera):
    """representation of a MQTT camera."""

    _entity_id_format = camera.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_CAMERA_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT Camera."""
        self._last_image = None

        Camera.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            if self._config[CONF_ENCODING] == "b64":
                self._last_image = b64decode(msg.payload)
            else:
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

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        return self._last_image
