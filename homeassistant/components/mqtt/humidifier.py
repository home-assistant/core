"""Support for MQTT humidifiers."""
from __future__ import annotations

from collections.abc import Callable
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import humidifier
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_STATE_VALUE_TEMPLATE,
    PAYLOAD_NONE,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    warn_for_legacy_schema,
)
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic

CONF_AVAILABLE_MODES_LIST = "modes"
CONF_DEVICE_CLASS = "device_class"
CONF_MODE_COMMAND_TEMPLATE = "mode_command_template"
CONF_MODE_COMMAND_TOPIC = "mode_command_topic"
CONF_MODE_STATE_TOPIC = "mode_state_topic"
CONF_MODE_STATE_TEMPLATE = "mode_state_template"
CONF_PAYLOAD_RESET_MODE = "payload_reset_mode"
CONF_PAYLOAD_RESET_HUMIDITY = "payload_reset_humidity"
CONF_TARGET_HUMIDITY_COMMAND_TEMPLATE = "target_humidity_command_template"
CONF_TARGET_HUMIDITY_COMMAND_TOPIC = "target_humidity_command_topic"
CONF_TARGET_HUMIDITY_MIN = "min_humidity"
CONF_TARGET_HUMIDITY_MAX = "max_humidity"
CONF_TARGET_HUMIDITY_STATE_TEMPLATE = "target_humidity_state_template"
CONF_TARGET_HUMIDITY_STATE_TOPIC = "target_humidity_state_topic"

DEFAULT_NAME = "MQTT Humidifier"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_RESET = "None"

MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED = frozenset(
    {
        humidifier.ATTR_HUMIDITY,
        humidifier.ATTR_MAX_HUMIDITY,
        humidifier.ATTR_MIN_HUMIDITY,
        humidifier.ATTR_MODE,
        humidifier.ATTR_AVAILABLE_MODES,
    }
)

_LOGGER = logging.getLogger(__name__)


def valid_mode_configuration(config: ConfigType) -> ConfigType:
    """Validate that the mode reset payload is not one of the available modes."""
    if config[CONF_PAYLOAD_RESET_MODE] in config[CONF_AVAILABLE_MODES_LIST]:
        raise ValueError("modes must not contain payload_reset_mode")
    return config


def valid_humidity_range_configuration(config: ConfigType) -> ConfigType:
    """Validate humidity range.

    Ensures that the target_humidity range configuration is valid,
    throws if it isn't.
    """
    if config[CONF_TARGET_HUMIDITY_MIN] >= config[CONF_TARGET_HUMIDITY_MAX]:
        raise ValueError("target_humidity_max must be > target_humidity_min")
    if config[CONF_TARGET_HUMIDITY_MAX] > 100:
        raise ValueError("max_humidity must be <= 100")

    return config


_PLATFORM_SCHEMA_BASE = MQTT_RW_SCHEMA.extend(
    {
        # CONF_AVAIALABLE_MODES_LIST and CONF_MODE_COMMAND_TOPIC must be used together
        vol.Inclusive(
            CONF_AVAILABLE_MODES_LIST, "available_modes", default=[]
        ): cv.ensure_list,
        vol.Inclusive(CONF_MODE_COMMAND_TOPIC, "available_modes"): valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(
            CONF_DEVICE_CLASS, default=HumidifierDeviceClass.HUMIDIFIER
        ): vol.In(
            [HumidifierDeviceClass.HUMIDIFIER, HumidifierDeviceClass.DEHUMIDIFIER]
        ),
        vol.Optional(CONF_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_MODE_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_TARGET_HUMIDITY_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_TARGET_HUMIDITY_COMMAND_TEMPLATE): cv.template,
        vol.Optional(
            CONF_TARGET_HUMIDITY_MAX, default=DEFAULT_MAX_HUMIDITY
        ): cv.positive_int,
        vol.Optional(
            CONF_TARGET_HUMIDITY_MIN, default=DEFAULT_MIN_HUMIDITY
        ): cv.positive_int,
        vol.Optional(CONF_TARGET_HUMIDITY_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(
            CONF_PAYLOAD_RESET_HUMIDITY, default=DEFAULT_PAYLOAD_RESET
        ): cv.string,
        vol.Optional(CONF_PAYLOAD_RESET_MODE, default=DEFAULT_PAYLOAD_RESET): cv.string,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Humidifiers under the humidifier platform key was deprecated in
# HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(
    warn_for_legacy_schema(humidifier.DOMAIN),
)

PLATFORM_SCHEMA_MODERN = vol.All(
    _PLATFORM_SCHEMA_BASE,
    valid_humidity_range_configuration,
    valid_mode_configuration,
)

DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    valid_humidity_range_configuration,
    valid_mode_configuration,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT humidifier through YAML and through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, humidifier.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT humidifier."""
    async_add_entities([MqttHumidifier(hass, config, config_entry, discovery_data)])


class MqttHumidifier(MqttEntity, HumidifierEntity):
    """A MQTT humidifier component."""

    _entity_id_format = humidifier.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED

    _command_templates: dict[str, Callable[[PublishPayloadType], PublishPayloadType]]
    _value_templates: dict[str, Callable[[ReceivePayloadType], ReceivePayloadType]]
    _optimistic: bool
    _optimistic_target_humidity: bool
    _optimistic_mode: bool
    _payload: dict[str, str]
    _topic: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the MQTT humidifier."""
        self._attr_mode = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_min_humidity = config[CONF_TARGET_HUMIDITY_MIN]
        self._attr_max_humidity = config[CONF_TARGET_HUMIDITY_MAX]

        self._topic = {
            key: config.get(key)
            for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_TARGET_HUMIDITY_STATE_TOPIC,
                CONF_TARGET_HUMIDITY_COMMAND_TOPIC,
                CONF_MODE_STATE_TOPIC,
                CONF_MODE_COMMAND_TOPIC,
            )
        }
        self._payload = {
            "STATE_ON": config[CONF_PAYLOAD_ON],
            "STATE_OFF": config[CONF_PAYLOAD_OFF],
            "HUMIDITY_RESET": config[CONF_PAYLOAD_RESET_HUMIDITY],
            "MODE_RESET": config[CONF_PAYLOAD_RESET_MODE],
        }
        if CONF_MODE_COMMAND_TOPIC in config and CONF_AVAILABLE_MODES_LIST in config:
            self._attr_available_modes = config[CONF_AVAILABLE_MODES_LIST]
        else:
            self._attr_available_modes = []
        if self._attr_available_modes:
            self._attr_supported_features = HumidifierEntityFeature.MODES

        optimistic: bool = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None
        self._optimistic_target_humidity = (
            optimistic or self._topic[CONF_TARGET_HUMIDITY_STATE_TOPIC] is None
        )
        self._optimistic_mode = optimistic or self._topic[CONF_MODE_STATE_TOPIC] is None

        self._command_templates = {}
        command_templates: dict[str, Template | None] = {
            CONF_STATE: config.get(CONF_COMMAND_TEMPLATE),
            ATTR_HUMIDITY: config.get(CONF_TARGET_HUMIDITY_COMMAND_TEMPLATE),
            ATTR_MODE: config.get(CONF_MODE_COMMAND_TEMPLATE),
        }
        for key, tpl in command_templates.items():
            self._command_templates[key] = MqttCommandTemplate(
                tpl, entity=self
            ).async_render

        self._value_templates = {}
        value_templates: dict[str, Template | None] = {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            ATTR_HUMIDITY: config.get(CONF_TARGET_HUMIDITY_STATE_TEMPLATE),
            ATTR_MODE: config.get(CONF_MODE_STATE_TEMPLATE),
        }
        for key, tpl in value_templates.items():
            self._value_templates[key] = MqttValueTemplate(
                tpl,
                entity=self,
            ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        topics: dict[str, Any] = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg: ReceiveMessage) -> None:
            """Handle new received MQTT message."""
            payload = self._value_templates[CONF_STATE](msg.payload)
            if not payload:
                _LOGGER.debug("Ignoring empty state from '%s'", msg.topic)
                return
            if payload == self._payload["STATE_ON"]:
                self._attr_is_on = True
            elif payload == self._payload["STATE_OFF"]:
                self._attr_is_on = False
            elif payload == PAYLOAD_NONE:
                self._attr_is_on = None
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._topic[CONF_STATE_TOPIC],
                "msg_callback": state_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }

        @callback
        @log_messages(self.hass, self.entity_id)
        def target_humidity_received(msg: ReceiveMessage) -> None:
            """Handle new received MQTT message for the target humidity."""
            rendered_target_humidity_payload = self._value_templates[ATTR_HUMIDITY](
                msg.payload
            )
            if not rendered_target_humidity_payload:
                _LOGGER.debug("Ignoring empty target humidity from '%s'", msg.topic)
                return
            if rendered_target_humidity_payload == self._payload["HUMIDITY_RESET"]:
                self._attr_target_humidity = None
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
                return
            try:
                target_humidity = round(float(rendered_target_humidity_payload))
            except ValueError:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid target humidity",
                    msg.payload,
                    msg.topic,
                    rendered_target_humidity_payload,
                )
                return
            if (
                target_humidity < self._attr_min_humidity
                or target_humidity > self._attr_max_humidity
            ):
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid target humidity",
                    msg.payload,
                    msg.topic,
                    rendered_target_humidity_payload,
                )
                return
            self._attr_target_humidity = target_humidity
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._topic[CONF_TARGET_HUMIDITY_STATE_TOPIC] is not None:
            topics[CONF_TARGET_HUMIDITY_STATE_TOPIC] = {
                "topic": self._topic[CONF_TARGET_HUMIDITY_STATE_TOPIC],
                "msg_callback": target_humidity_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
            self._attr_target_humidity = None

        @callback
        @log_messages(self.hass, self.entity_id)
        def mode_received(msg: ReceiveMessage) -> None:
            """Handle new received MQTT message for mode."""
            mode = str(self._value_templates[ATTR_MODE](msg.payload))
            if mode == self._payload["MODE_RESET"]:
                self._attr_mode = None
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
                return
            if not mode:
                _LOGGER.debug("Ignoring empty mode from '%s'", msg.topic)
                return
            if not self.available_modes or mode not in self.available_modes:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid mode",
                    msg.payload,
                    msg.topic,
                    mode,
                )
                return

            self._attr_mode = mode
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._topic[CONF_MODE_STATE_TOPIC] is not None:
            topics[CONF_MODE_STATE_TOPIC] = {
                "topic": self._topic[CONF_MODE_STATE_TOPIC],
                "msg_callback": mode_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }
            self._attr_mode = None

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_ON"])
        await self.async_publish(
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_OFF"])
        await self.async_publish(
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )
        if self._optimistic:
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the humidifier.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[ATTR_HUMIDITY](humidity)
        await self.async_publish(
            self._topic[CONF_TARGET_HUMIDITY_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic_target_humidity:
            self._attr_target_humidity = humidity
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan.

        This method is a coroutine.
        """
        if not self.available_modes or mode not in self.available_modes:
            _LOGGER.warning("'%s'is not a valid mode", mode)
            return

        mqtt_payload = self._command_templates[ATTR_MODE](mode)

        await self.async_publish(
            self._topic[CONF_MODE_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic_mode:
            self._attr_mode = mode
            self.async_write_ha_state()
