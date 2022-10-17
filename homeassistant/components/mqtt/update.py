"""Configure update platform in a device through MQTT topic."""
from __future__ import annotations

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
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_BASE_SCHEMA
from .const import CONF_COMMAND_TOPIC, CONF_ENCODING, CONF_QOS, CONF_RETAIN
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper
from .models import MqttValueTemplate
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Update"

CONF_INSTALLED_VERSION_TEMPLATE = "installed_version_template"
CONF_INSTALLED_VERSION_TOPIC = "installed_version_topic"
CONF_LATEST_VERSION_TEMPLATE = "latest_version_template"
CONF_LATEST_VERSION_TOPIC = "latest_version_topic"
CONF_PAYLOAD_INSTALL = "payload_install"


PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_INSTALLED_VERSION_TEMPLATE): cv.template,
        vol.Optional(CONF_INSTALLED_VERSION_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_LATEST_VERSION_TEMPLATE): cv.template,
        vol.Required(CONF_LATEST_VERSION_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_INSTALL): cv.string,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
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
    config_entry: ConfigEntry | None = None,
    discovery_data: dict | None = None,
) -> None:
    """Set up the MQTT update."""
    async_add_entities([MqttUpdate(hass, config, config_entry, discovery_data)])


class MqttUpdate(MqttEntity, UpdateEntity, RestoreEntity):
    """representation of an MQTT update."""

    _entity_id_format = update.ENTITY_ID_FORMAT

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT update."""
        self._config = config
        self._sub_state = None

        self._attr_device_class = self._config.get(CONF_DEVICE_CLASS)

        UpdateEntity.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._templates = {
            CONF_INSTALLED_VERSION_TEMPLATE: MqttValueTemplate(
                config.get(CONF_INSTALLED_VERSION_TEMPLATE),
                entity=self,
            ).async_render_with_possible_json_value,
            CONF_LATEST_VERSION_TEMPLATE: MqttValueTemplate(
                config.get(CONF_LATEST_VERSION_TEMPLATE),
                entity=self,
            ).async_render_with_possible_json_value,
        }

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        def add_subscription(topics, topic, msg_callback):
            if self._config.get(topic) is not None:
                topics[topic] = {
                    "topic": self._config[topic],
                    "msg_callback": msg_callback,
                    "qos": self._config[CONF_QOS],
                    "encoding": self._config[CONF_ENCODING] or None,
                }

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_installed_version_received(msg):
            """Handle receiving installed version via MQTT."""
            installed_version = self._templates[CONF_INSTALLED_VERSION_TEMPLATE](
                msg.payload
            )
            self._attr_installed_version = installed_version

            self.async_write_ha_state()

        add_subscription(
            topics, CONF_INSTALLED_VERSION_TOPIC, handle_installed_version_received
        )

        @callback
        @log_messages(self.hass, self.entity_id)
        def handle_latest_version_received(msg):
            """Handle receiving latest version via MQTT."""
            latest_version = self._templates[CONF_LATEST_VERSION_TEMPLATE](msg.payload)
            self._attr_latest_version = latest_version

            self.async_write_ha_state()

        add_subscription(
            topics, CONF_LATEST_VERSION_TOPIC, handle_latest_version_received
        )

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self):
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

        self.async_write_ha_state()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        support = 0

        if self._config.get(CONF_COMMAND_TOPIC) is not None:
            support |= UpdateEntityFeature.INSTALL

        return support
