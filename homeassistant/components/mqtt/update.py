"""Configure update platform in a device through MQTT topic."""

from __future__ import annotations

import logging
from typing import Any, TypedDict, cast

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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, VolSchemaType
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from . import subscription
from .config import DEFAULT_RETAIN, MQTT_RO_SCHEMA
from .const import CONF_COMMAND_TOPIC, CONF_RETAIN, CONF_STATE_TOPIC, PAYLOAD_EMPTY_JSON
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import MqttValueTemplate, ReceiveMessage
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

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
        vol.Optional(CONF_DEVICE_CLASS): vol.Any(DEVICE_CLASSES_SCHEMA, None),
        vol.Optional(CONF_ENTITY_PICTURE): cv.string,
        vol.Optional(CONF_LATEST_VERSION_TEMPLATE): cv.template,
        vol.Optional(CONF_LATEST_VERSION_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_PAYLOAD_INSTALL): cv.string,
        vol.Optional(CONF_RELEASE_SUMMARY): cv.string,
        vol.Optional(CONF_RELEASE_URL): cv.string,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_TITLE): cv.string,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)


DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


class _MqttUpdatePayloadType(TypedDict, total=False):
    """Presentation of supported JSON payload to process state updates."""

    installed_version: str
    latest_version: str
    title: str
    release_summary: str
    release_url: str
    entity_picture: str


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT update entity through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttUpdate,
        update.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttUpdate(MqttEntity, UpdateEntity, RestoreEntity):
    """Representation of the MQTT update entity."""

    _default_name = DEFAULT_NAME
    _entity_id_format = update.ENTITY_ID_FORMAT
    _entity_picture: str | None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend."""
        if self._entity_picture is not None:
            return self._entity_picture

        return super().entity_picture

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_device_class = self._config.get(CONF_DEVICE_CLASS)
        self._attr_release_summary = self._config.get(CONF_RELEASE_SUMMARY)
        self._attr_release_url = self._config.get(CONF_RELEASE_URL)
        self._attr_title = self._config.get(CONF_TITLE)
        self._entity_picture: str | None = self._config.get(CONF_ENTITY_PICTURE)
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

    @callback
    def _handle_state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving state message via MQTT."""
        payload = self._templates[CONF_VALUE_TEMPLATE](msg.payload)

        if not payload or payload == PAYLOAD_EMPTY_JSON:
            _LOGGER.debug(
                "Ignoring empty payload '%s' after rendering for topic %s",
                payload,
                msg.topic,
            )
            return

        json_payload: _MqttUpdatePayloadType = {}
        try:
            rendered_json_payload = json_loads(payload)
            if isinstance(rendered_json_payload, dict):
                _LOGGER.debug(
                    (
                        "JSON payload detected after processing payload '%s' on"
                        " topic %s"
                    ),
                    rendered_json_payload,
                    msg.topic,
                )
                json_payload = cast(_MqttUpdatePayloadType, rendered_json_payload)
            else:
                _LOGGER.debug(
                    (
                        "Non-dictionary JSON payload detected after processing"
                        " payload '%s' on topic %s"
                    ),
                    payload,
                    msg.topic,
                )
                json_payload = {"installed_version": str(payload)}
        except JSON_DECODE_EXCEPTIONS:
            _LOGGER.debug(
                (
                    "No valid (JSON) payload detected after processing payload '%s'"
                    " on topic %s"
                ),
                payload,
                msg.topic,
            )
            json_payload["installed_version"] = str(payload)

        if "installed_version" in json_payload:
            self._attr_installed_version = json_payload["installed_version"]

        if "latest_version" in json_payload:
            self._attr_latest_version = json_payload["latest_version"]

        if "title" in json_payload:
            self._attr_title = json_payload["title"]

        if "release_summary" in json_payload:
            self._attr_release_summary = json_payload["release_summary"]

        if "release_url" in json_payload:
            self._attr_release_url = json_payload["release_url"]

        if "entity_picture" in json_payload:
            self._entity_picture = json_payload["entity_picture"]

    @callback
    def _handle_latest_version_received(self, msg: ReceiveMessage) -> None:
        """Handle receiving latest version via MQTT."""
        latest_version = self._templates[CONF_LATEST_VERSION_TEMPLATE](msg.payload)

        if isinstance(latest_version, str) and latest_version != "":
            self._attr_latest_version = latest_version

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        self.add_subscription(
            CONF_STATE_TOPIC,
            self._handle_state_message_received,
            {
                "_attr_installed_version",
                "_attr_latest_version",
                "_attr_title",
                "_attr_release_summary",
                "_attr_release_url",
                "_entity_picture",
            },
        )
        self.add_subscription(
            CONF_LATEST_VERSION_TOPIC,
            self._handle_latest_version_received,
            {"_attr_latest_version"},
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Update the current value."""
        payload = self._config[CONF_PAYLOAD_INSTALL]
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Return the list of supported features."""
        support = UpdateEntityFeature(0)

        if self._config.get(CONF_COMMAND_TOPIC) is not None:
            support |= UpdateEntityFeature.INSTALL

        return support
