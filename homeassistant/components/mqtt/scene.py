"""Support for MQTT scenes."""

from typing import Any, override

import probatio

from homeassistant.components import scene
from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PAYLOAD_ON, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .config import MQTT_BASE_SCHEMA
from .const import CONF_COMMAND_TOPIC, CONF_RETAIN
from .entity import MqttEntity, async_setup_entity_entry_helper
from .schemas import mqtt_entity_common_schema
from .util import valid_publish_topic

PARALLEL_UPDATES = 0

DEFAULT_NAME = "MQTT Scene"
DEFAULT_RETAIN = False

ENTITY_ID_FORMAT = scene.DOMAIN + ".{}"

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_NAME): probatio.Any(cv.string, None),
        probatio.Optional(CONF_PAYLOAD_ON): cv.string,
        probatio.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    }
).extend(mqtt_entity_common_schema(Platform.SCENE).schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=probatio.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT scene through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttScene,
        scene.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttScene(
    MqttEntity,
    Scene,
):
    """Representation of a scene that can be activated using MQTT."""

    _default_name = DEFAULT_NAME
    _entity_id_format = scene.DOMAIN + ".{}"

    @staticmethod
    @override
    def config_schema() -> probatio.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @override
    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""

    @callback
    @override
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    @override
    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    @override
    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene.

        This method is a coroutine.
        """
        await self.async_publish_with_config(
            self._config[CONF_COMMAND_TOPIC], self._config[CONF_PAYLOAD_ON]
        )
