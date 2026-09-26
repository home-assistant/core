"""Support for MQTT notify."""

from typing import override

import probatio

from homeassistant.components import notify
from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import CONF_COMMAND_TEMPLATE, CONF_COMMAND_TOPIC, CONF_RETAIN
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import MqttCommandTemplate
from .schemas import mqtt_entity_common_schema
from .util import valid_publish_topic

PARALLEL_UPDATES = 0

DEFAULT_NAME = "MQTT notify"

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        probatio.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_NAME): probatio.Any(cv.string, None),
        probatio.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    }
).extend(mqtt_entity_common_schema(Platform.NOTIFY).schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=probatio.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT notify through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttNotify,
        notify.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttNotify(MqttEntity, NotifyEntity):
    """Notification entity that can send messages using MQTT."""

    _default_name = DEFAULT_NAME
    _entity_id_format = notify.ENTITY_ID_FORMAT

    @staticmethod
    @override
    def config_schema() -> probatio.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    @override
    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE), entity=self
        ).async_render

    @callback
    @override
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    @override
    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        payload = self._command_template(message)
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)
