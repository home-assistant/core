"""Support for MQTT sirens."""
from __future__ import annotations

import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import notify, siren
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
)
from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import (
    ATTR_AVAILABLE_TONES,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SUPPORT_DURATION,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    CONF_TARGET,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORMS, MqttCommandTemplate, MqttValueTemplate, subscription
from .. import mqtt
from .const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DOMAIN,
)
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

DEFAULT_NAME = "MQTT Siren"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_OPTIMISTIC = False

ENTITY_ID_FORMAT = siren.DOMAIN + ".{}"

CONF_AVAILABLE_TONES = "available_tones"
CONF_COMMAND_TEMPLATE = "command_template"
CONF_COMMAND_OFF_TEMPLATE = "command_off_template"
CONF_DURATION_COMMAND_TEMPLATE = "duration_command_template"
CONF_DURATION_COMMAND_TOPIC = "duration_command_topic"
CONF_MESSAGE_COMMAND_TEMPLATE = "message_command_template"
CONF_MESSAGE_COMMAND_TOPIC = "message_command_topic"
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"
CONF_SUPPORT_DURATION = "supported_duration"
CONF_SUPPORT_TURN_OFF = "supported_turn_off"
CONF_SUPPORT_TURN_ON = "supported_turn_on"
CONF_SUPPORT_VOLUME_SET = "supported_volume_set"
CONF_TITLE = "title"
CONF_TONE_COMMAND_TEMPLATE = "tone_command_template"
CONF_TONE_COMMAND_TOPIC = "tone_command_topic"
CONF_VOLUME_COMMAND_TEMPLATE = "volume_command_template"
CONF_VOLUME_COMMAND_TOPIC = "volume_command_topic"

MQTT_NOTIFY_CONFIG = "mqtt_notify_config"

SIREN_ENTITY = "siren_entity"


def valid_tone_configuration(config):
    """Validate that the preset mode reset payload is not one of the preset modes."""
    if CONF_TONE_COMMAND_TOPIC in config and not config.get(CONF_AVAILABLE_TONES):
        raise ValueError(
            "Available_tones must contain a valid list of available tones when tone_command_topic is configured"
        )
    return config


_PLATFORM_SCHEMA_BASE = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_AVAILABLE_TONES): cv.ensure_list,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_OFF_TEMPLATE): cv.template,
        vol.Optional(CONF_DURATION_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_DURATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_MESSAGE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_MESSAGE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_OFF): cv.string,
        vol.Optional(CONF_STATE_ON): cv.string,
        vol.Optional(CONF_SUPPORT_DURATION, default=True): cv.boolean,
        vol.Optional(CONF_SUPPORT_TURN_OFF, default=True): cv.boolean,
        vol.Optional(CONF_SUPPORT_TURN_ON, default=True): cv.boolean,
        vol.Optional(CONF_SUPPORT_VOLUME_SET, default=True): cv.boolean,
        vol.Optional(CONF_TARGET): cv.string,
        vol.Optional(CONF_TITLE): cv.string,
        vol.Optional(CONF_TONE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TONE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VOLUME_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_VOLUME_COMMAND_TOPIC): mqtt.valid_publish_topic,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
PLATFORM_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE,
    valid_tone_configuration,
)

DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA), valid_tone_configuration
)

MQTT_SIREN_ATTRIBUTES_BLOCKED = frozenset(
    {
        ATTR_AVAILABLE_TONES,
        ATTR_DATA,
        ATTR_DURATION,
        ATTR_MESSAGE,
        ATTR_TARGET,
        ATTR_TITLE,
        ATTR_TITLE_DEFAULT,
        ATTR_TONE,
        ATTR_VOLUME_LEVEL,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT siren through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT siren dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, siren.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT siren."""
    async_add_entities([MqttSiren(hass, config, config_entry, discovery_data)])


class MqttSiren(MqttEntity, SirenEntity):
    """Representation of a siren that can be toggled and notified using MQTT."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_SIREN_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT siren."""
        self._attr_name = config[CONF_NAME]
        self._attr_should_poll = False
        self._supported_features = 0
        self._attr_is_on = False
        self._attr_extra_state_attributes = {}

        self._state_on = None
        self._state_off = None
        self._available_tones = None
        self._tone = None
        self._duration = None
        self._volume_level = None
        self._optimistic = None
        self._support_tones = None

        self.target = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    async def async_removed_from_registry(self):
        """Remove the notify service registration."""
        if not self.target:
            return
        del self.hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA][self.target]
        await self.hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE].async_register_services()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""

        state_on = config.get(CONF_STATE_ON)
        self._state_on = state_on if state_on else config[CONF_PAYLOAD_ON]

        state_off = config.get(CONF_STATE_OFF)
        self._state_off = state_off if state_off else config[CONF_PAYLOAD_OFF]

        if config[CONF_SUPPORT_DURATION]:
            self._supported_features |= SUPPORT_DURATION
        if config[CONF_SUPPORT_TURN_OFF]:
            self._supported_features |= SUPPORT_TURN_OFF
        if config[CONF_SUPPORT_TURN_ON]:
            self._supported_features |= SUPPORT_TURN_ON
        if config[CONF_SUPPORT_VOLUME_SET]:
            self._supported_features |= SUPPORT_VOLUME_SET

        self._support_tones = CONF_AVAILABLE_TONES in config
        if self._support_tones:
            self._supported_features |= SUPPORT_TONES
            self._attr_available_tones = config[CONF_AVAILABLE_TONES]

        self._optimistic = config[CONF_OPTIMISTIC] or CONF_STATE_TOPIC not in config

        self._command_templates = {
            CONF_COMMAND_TEMPLATE: config.get(CONF_COMMAND_TEMPLATE),
            CONF_COMMAND_OFF_TEMPLATE: config.get(CONF_COMMAND_OFF_TEMPLATE)
            or config.get(CONF_COMMAND_TEMPLATE),
            CONF_DURATION_COMMAND_TEMPLATE: config.get(CONF_DURATION_COMMAND_TEMPLATE),
            CONF_TONE_COMMAND_TEMPLATE: config.get(CONF_TONE_COMMAND_TEMPLATE),
            CONF_VOLUME_COMMAND_TEMPLATE: config.get(CONF_VOLUME_COMMAND_TEMPLATE),
        }
        for key, tpl in self._command_templates.items():
            self._command_templates[key] = MqttCommandTemplate(
                tpl, entity=self
            ).async_render
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

        # integration notify platform
        if config.get(CONF_MESSAGE_COMMAND_TOPIC):
            notify_config = {
                SIREN_ENTITY: self,
                CONF_MESSAGE_COMMAND_TOPIC: config[CONF_MESSAGE_COMMAND_TOPIC],
                CONF_RETAIN: config[CONF_RETAIN],
                CONF_QOS: config[CONF_QOS],
                CONF_ENCODING: config[CONF_ENCODING],
            }
            if CONF_MESSAGE_COMMAND_TEMPLATE in config:
                notify_config[CONF_MESSAGE_COMMAND_TEMPLATE] = config[
                    CONF_MESSAGE_COMMAND_TEMPLATE
                ].template
            if CONF_NAME in config:
                notify_config[CONF_NAME] = config[CONF_NAME]
            if CONF_TARGET in config:
                notify_config[CONF_TARGET] = config[CONF_TARGET]
            if CONF_TITLE in config:
                notify_config[CONF_TITLE] = config[CONF_TITLE]
            self.hass.async_create_task(
                async_load_platform(
                    self.hass, notify.DOMAIN, DOMAIN, notify_config, config
                )
            )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = self._value_template(msg.payload)
            if payload == self._state_on:
                self._attr_is_on = True
            elif payload == self._state_off:
                self._attr_is_on = False

            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    CONF_STATE_TOPIC: {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": state_message_received,
                        "qos": self._config[CONF_QOS],
                        "encoding": self._config[CONF_ENCODING] or None,
                    }
                },
            )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    async def async_conditional_publish(
        self, topic: str, template: str, value: Any, variables: dict | None = None
    ) -> None:
        """Publish MQTT payload with command template if a topic is configured."""
        if self._config.get(topic) and value:
            payload = self._command_templates[template](value, variables)

            await mqtt.async_publish(
                self.hass,
                self._config[topic],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the siren on.

        This method is a coroutine.
        """
        await self.async_conditional_publish(
            CONF_COMMAND_TOPIC,
            CONF_COMMAND_TEMPLATE,
            self._config[CONF_PAYLOAD_ON],
            kwargs,
        )
        if self._optimistic:
            # Optimistically assume that siren has changed state.
            self._attr_is_on = True
            self.async_write_ha_state()

        if not kwargs:
            return

        await self.async_conditional_publish(
            CONF_DURATION_COMMAND_TOPIC,
            CONF_DURATION_COMMAND_TEMPLATE,
            kwargs.get(ATTR_DURATION),
        )
        await self.async_conditional_publish(
            CONF_TONE_COMMAND_TOPIC,
            CONF_TONE_COMMAND_TEMPLATE,
            kwargs.get(ATTR_TONE),
        )
        await self.async_conditional_publish(
            CONF_VOLUME_COMMAND_TOPIC,
            CONF_VOLUME_COMMAND_TEMPLATE,
            kwargs.get(ATTR_VOLUME_LEVEL),
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the siren off.

        This method is a coroutine.
        """
        await self.async_conditional_publish(
            CONF_COMMAND_TOPIC,
            CONF_COMMAND_OFF_TEMPLATE,
            self._config[CONF_PAYLOAD_OFF],
        )

        if self._optimistic:
            # Optimistically assume that siren has changed state.
            self._attr_is_on = False
            self.async_write_ha_state()
