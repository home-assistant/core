"""Support for MQTT sirens."""
from __future__ import annotations

from curses import keyname
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import notify, siren
from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import (
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

CONF_AVAILABLE_TONES = "available_tones"
CONF_COMMAND_TEMPLATE = "command_template"
CONF_DURATION_COMMAND_TEMPLATE = "duration_command_template"
CONF_DURATION_COMMAND_TOPIC = "duration_command_topic"
CONF_DURATION_STATE_TOPIC = "duration_state_topic"
CONF_DURATION_VALUE_TEMPLATE = "duration_value_template"
CONF_MESSAGE_COMMAND_TEMPLATE = "message_command_template"
CONF_MESSAGE_COMMAND_TOPIC = "message_command_topic"
CONF_MESSAGE_STATE_TOPIC = "message_state_topic"
CONF_MESSAGE_VALUE_TEMPLATE = "message_value_template"
CONF_SIREN_ENTITY = "siren_entity"
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"
CONF_TITLE = "title"
CONF_TONE_COMMAND_TEMPLATE = "tone_command_template"
CONF_TONE_COMMAND_TOPIC = "tone_command_topic"
CONF_TONE_STATE_TOPIC = "tone_state_topic"
CONF_TONE_VALUE_TEMPLATE = "tone_value_template"
CONF_VOLUME_COMMAND_TEMPLATE = "volume_command_template"
CONF_VOLUME_COMMAND_TOPIC = "volume_command_topic"
CONF_VOLUME_STATE_TOPIC = "volume_state_topic"
CONF_VOLUME_VALUE_TEMPLATE = "volume_value_template"

MQTT_NOTIFY_CONFIG = "mqtt_notify_config"

ENTITY_ID_FORMAT = siren.DOMAIN + ".{}"

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_AVAILABLE_TONES, default=[]): cv.ensure_list,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_DURATION_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_DURATION_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_DURATION_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_DURATION_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_MESSAGE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_MESSAGE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_MESSAGE_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_MESSAGE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_OFF): cv.string,
        vol.Optional(CONF_STATE_ON): cv.string,
        vol.Optional(CONF_TARGET): cv.string,
        vol.Optional(CONF_TITLE): cv.string,
        vol.Optional(CONF_TONE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_TONE_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_TONE_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_TONE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_VOLUME_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_VOLUME_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_VOLUME_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_VOLUME_VALUE_TEMPLATE): cv.template,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA.extend({}, extra=vol.REMOVE_EXTRA)

SUPPORT_FLAGS = (
    SUPPORT_DURATION | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | SUPPORT_VOLUME_SET
)

MQTT_SIREN_ATTRIBUTES_BLOCKED = frozenset(
    {
        notify.ATTR_DATA,
        notify.ATTR_MESSAGE,
        notify.ATTR_TARGET,
        notify.ATTR_TITLE,
        notify.ATTR_TITLE_DEFAULT,
        notify.ATTR_TARGET,
        siren.ATTR_AVAILABLE_TONES,
        siren.ATTR_DURATION,
        siren.ATTR_TONE,
        siren.ATTR_VOLUME_LEVEL,
    }
)

_LOGGER = logging.getLogger(__name__)


def valid_siren_entity(value: Any) -> MqttSiren:
    """Validate if the value passed is a valid MqttSiren object."""
    if not isinstance(value, MqttSiren):
        raise vol.Invalid(f"Object {value} is not a valid MqttSiren entity")
    return value


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
        self._supported_features = SUPPORT_FLAGS
        self._attr_is_on = False
        self._attr_extra_state_attributes = {}

        self._state_on = None
        self._state_off = None
        self._available_tones = None
        self._target = None
        self._tone = None
        self._duration = None
        self._volume_level = None
        self._optimistic = None
        self._support_tones = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    async def async_removed_from_registry(self):
        """Remove the notify service registration."""
        if not self._target:
            return
        del self.hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE_DATA][self._target]
        await self.hass.data[MQTT_NOTIFY_CONFIG][CONF_SERVICE].async_register_services()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""

        state_on = config.get(CONF_STATE_ON)
        self._state_on = state_on if state_on else config[CONF_PAYLOAD_ON]

        state_off = config.get(CONF_STATE_OFF)
        self._state_off = state_off if state_off else config[CONF_PAYLOAD_OFF]

        self._optimistic = config[CONF_OPTIMISTIC] or CONF_STATE_TOPIC not in config

        self._topic = {
            key: config.get(keyname)
            for key in (
                CONF_COMMAND_TOPIC,
                CONF_DURATION_STATE_TOPIC,
                CONF_DURATION_COMMAND_TOPIC,
                CONF_MESSAGE_COMMAND_TOPIC,
                CONF_MESSAGE_STATE_TOPIC,
                CONF_STATE_TOPIC,
                CONF_TONE_COMMAND_TOPIC,
                CONF_TONE_STATE_TOPIC,
                CONF_VOLUME_COMMAND_TOPIC,
                CONF_VOLUME_STATE_TOPIC,
            )
        }
        self._command_templates = {
            CONF_COMMAND_TEMPLATE: config.get(CONF_COMMAND_TEMPLATE),
            CONF_DURATION_COMMAND_TEMPLATE: config.get(CONF_DURATION_COMMAND_TEMPLATE),
            CONF_MESSAGE_COMMAND_TEMPLATE: config.get(CONF_MESSAGE_COMMAND_TEMPLATE),
            CONF_TONE_COMMAND_TEMPLATE: config.get(CONF_TONE_COMMAND_TEMPLATE),
            CONF_VOLUME_COMMAND_TEMPLATE: config.get(CONF_VOLUME_COMMAND_TEMPLATE),
        }
        self._value_templates = {
            CONF_DURATION_VALUE_TEMPLATE: config.get(CONF_DURATION_VALUE_TEMPLATE),
            CONF_MESSAGE_VALUE_TEMPLATE: config.get(CONF_MESSAGE_VALUE_TEMPLATE),
            CONF_TONE_VALUE_TEMPLATE: config.get(CONF_TONE_VALUE_TEMPLATE),
            CONF_VALUE_TEMPLATE: config.get(CONF_VALUE_TEMPLATE),
            CONF_VOLUME_VALUE_TEMPLATE: config.get(CONF_VOLUME_VALUE_TEMPLATE),
        }
        self._support_tones = bool(CONF_AVAILABLE_TONES in config)
        if self._support_tones:
            self._supported_features |= SUPPORT_TONES
            self._attr_available_tones = config[CONF_AVAILABLE_TONES]

        for key, tpl in self._command_templates.items():
            self._command_templates[key] = MqttCommandTemplate(
                tpl, entity=self
            ).async_render

        for key, tpl in self._value_templates.items():
            self._value_templates[key] = MqttValueTemplate(
                tpl,
                entity=self,
            ).async_render_with_possible_json_value

        if config.get(CONF_MESSAGE_COMMAND_TOPIC):
            notify_config = {
                CONF_SIREN_ENTITY: self,
                CONF_MESSAGE_COMMAND_TOPIC: config[CONF_MESSAGE_COMMAND_TOPIC],
                CONF_RETAIN: config[CONF_RETAIN],
                CONF_QOS: config[CONF_QOS],
                CONF_ENCODING: config[CONF_ENCODING],
            }
            if hasattr(config, CONF_MESSAGE_COMMAND_TEMPLATE):
                notify_config[CONF_MESSAGE_COMMAND_TEMPLATE] = config[
                    CONF_MESSAGE_COMMAND_TEMPLATE
                ]
            if hasattr(config, CONF_NAME):
                notify_config[CONF_NAME] = config[CONF_NAME]
            if hasattr(config, CONF_TARGET):
                notify_config[CONF_TARGET] = config[CONF_TARGET]
            if hasattr(config, CONF_TITLE):
                notify_config[CONF_TITLE] = config[CONF_TITLE]
            self.hass.async_create_task(
                async_load_platform(
                    self.hass, notify.DOMAIN, DOMAIN, notify_config, config
                )
            )
            self._target = (
                notify_config.get(CONF_TARGET)
                or notify_config[CONF_MESSAGE_COMMAND_TOPIC]
            )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = self._value_templates[CONF_VALUE_TEMPLATE](msg.payload)
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

    async def async_turn_on(self, **kwargs):
        """Turn the siren on.

        This method is a coroutine.
        """
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_ON],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that siren has changed state.
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the siren off.

        This method is a coroutine.
        """
        await mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_PAYLOAD_OFF],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            # Optimistically assume that siren has changed state.
            self._attr_is_on = False
            self.async_write_ha_state()
