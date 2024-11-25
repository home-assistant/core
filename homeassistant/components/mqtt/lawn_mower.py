"""Support for MQTT lawn mowers."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
import logging

import voluptuous as vol

from homeassistant.components import lawn_mower
from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from . import subscription
from .config import MQTT_BASE_SCHEMA
from .const import CONF_RETAIN, DEFAULT_OPTIMISTIC, DEFAULT_RETAIN
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_COMMON_SCHEMA
from .util import valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

CONF_ACTIVITY_STATE_TOPIC = "activity_state_topic"
CONF_ACTIVITY_VALUE_TEMPLATE = "activity_value_template"
CONF_DOCK_COMMAND_TOPIC = "dock_command_topic"
CONF_DOCK_COMMAND_TEMPLATE = "dock_command_template"
CONF_PAUSE_COMMAND_TOPIC = "pause_command_topic"
CONF_PAUSE_COMMAND_TEMPLATE = "pause_command_template"
CONF_START_MOWING_COMMAND_TOPIC = "start_mowing_command_topic"
CONF_START_MOWING_COMMAND_TEMPLATE = "start_mowing_command_template"

DEFAULT_NAME = "MQTT Lawn Mower"
ENTITY_ID_FORMAT = lawn_mower.DOMAIN + ".{}"

MQTT_LAWN_MOWER_ATTRIBUTES_BLOCKED: frozenset[str] = frozenset()

FEATURE_DOCK = "dock"
FEATURE_PAUSE = "pause"
FEATURE_START_MOWING = "start_mowing"

PLATFORM_SCHEMA_MODERN = MQTT_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_ACTIVITY_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ACTIVITY_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_DOCK_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_DOCK_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAUSE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_PAUSE_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_START_MOWING_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_START_MOWING_COMMAND_TOPIC): valid_publish_topic,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT lawn mower through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttLawnMower,
        lawn_mower.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttLawnMower(MqttEntity, LawnMowerEntity, RestoreEntity):
    """Representation of an MQTT lawn mower."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LAWN_MOWER_ATTRIBUTES_BLOCKED
    _command_templates: dict[str, Callable[[PublishPayloadType], PublishPayloadType]]
    _command_topics: dict[str, str]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_assumed_state = config[CONF_OPTIMISTIC]

        self._value_template = MqttValueTemplate(
            config.get(CONF_ACTIVITY_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value
        supported_features = LawnMowerEntityFeature(0)
        self._command_topics = {}
        if CONF_DOCK_COMMAND_TOPIC in config:
            self._command_topics[FEATURE_DOCK] = config[CONF_DOCK_COMMAND_TOPIC]
            supported_features |= LawnMowerEntityFeature.DOCK
        if CONF_PAUSE_COMMAND_TOPIC in config:
            self._command_topics[FEATURE_PAUSE] = config[CONF_PAUSE_COMMAND_TOPIC]
            supported_features |= LawnMowerEntityFeature.PAUSE
        if CONF_START_MOWING_COMMAND_TOPIC in config:
            self._command_topics[FEATURE_START_MOWING] = config[
                CONF_START_MOWING_COMMAND_TOPIC
            ]
            supported_features |= LawnMowerEntityFeature.START_MOWING
        self._attr_supported_features = supported_features
        self._command_templates = {}
        self._command_templates[FEATURE_DOCK] = MqttCommandTemplate(
            config.get(CONF_DOCK_COMMAND_TEMPLATE), entity=self
        ).async_render
        self._command_templates[FEATURE_PAUSE] = MqttCommandTemplate(
            config.get(CONF_PAUSE_COMMAND_TEMPLATE), entity=self
        ).async_render
        self._command_templates[FEATURE_START_MOWING] = MqttCommandTemplate(
            config.get(CONF_START_MOWING_COMMAND_TEMPLATE), entity=self
        ).async_render

    @callback
    def _message_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT messages."""
        payload = str(self._value_template(msg.payload))
        if not payload:
            _LOGGER.debug(
                "Invalid empty activity payload from topic %s, for entity %s",
                msg.topic,
                self.entity_id,
            )
            return
        if payload.lower() == "none":
            self._attr_activity = None
            return

        try:
            self._attr_activity = LawnMowerActivity(payload)
        except ValueError:
            _LOGGER.error(
                "Invalid activity for %s: '%s' (valid activities: %s)",
                self.entity_id,
                payload,
                [option.value for option in LawnMowerActivity],
            )
            return

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        if not self.add_subscription(
            CONF_ACTIVITY_STATE_TOPIC, self._message_received, {"_attr_activity"}
        ):
            # Force into optimistic mode.
            self._attr_assumed_state = True
            return

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

        if self._attr_assumed_state and (
            last_state := await self.async_get_last_state()
        ):
            with contextlib.suppress(ValueError):
                self._attr_activity = LawnMowerActivity(last_state.state)

    async def _async_operate(self, option: str, activity: LawnMowerActivity) -> None:
        """Execute operation."""
        payload = self._command_templates[option](option)
        if self._attr_assumed_state:
            self._attr_activity = activity
            self.async_write_ha_state()
        await self.async_publish_with_config(self._command_topics[option], payload)

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        await self._async_operate("start_mowing", LawnMowerActivity.MOWING)

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self._async_operate("dock", LawnMowerActivity.DOCKED)

    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        await self._async_operate("pause", LawnMowerActivity.PAUSED)
