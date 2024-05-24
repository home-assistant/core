"""Support for MQTT notify."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
)
from .mixins import MqttEntity, async_setup_entity_entry_helper
from .models import MqttCommandTemplate
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic

DEFAULT_NAME = "MQTT notify"

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT notify through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttNotify,
        notify.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttNotify(MqttEntity, NotifyEntity):
    """Representation of a notification entity service that can send messages using MQTT."""

    _default_name = DEFAULT_NAME
    _entity_id_format = notify.ENTITY_ID_FORMAT

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE), entity=self
        ).async_render

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        payload = self._command_template(message)
        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
