"""Support for MQTT humidifiers."""
import functools
import logging

import voluptuous as vol

from homeassistant.components import humidifier
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    SUPPORT_MODES,
    HumidifierEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from . import PLATFORMS, subscription
from .. import mqtt
from .const import CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN, CONF_STATE_TOPIC, DOMAIN
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

CONF_AVAILABLE_MODES_LIST = "modes"
CONF_COMMAND_TEMPLATE = "command_template"
CONF_DEVICE_CLASS = "device_class"
CONF_MODE_COMMAND_TEMPLATE = "mode_command_template"
CONF_MODE_COMMAND_TOPIC = "mode_command_topic"
CONF_MODE_STATE_TOPIC = "mode_state_topic"
CONF_MODE_STATE_TEMPLATE = "mode_state_template"
CONF_PAYLOAD_RESET_MODE = "payload_reset_mode"
CONF_PAYLOAD_RESET_HUMIDITY = "payload_reset_humidity"
CONF_STATE_VALUE_TEMPLATE = "state_value_template"
CONF_TARGET_HUMIDITY_COMMAND_TEMPLATE = "target_humidity_command_template"
CONF_TARGET_HUMIDITY_COMMAND_TOPIC = "target_humidity_command_topic"
CONF_TARGET_HUMIDITY_MIN = "min_humidity"
CONF_TARGET_HUMIDITY_MAX = "max_humidity"
CONF_TARGET_HUMIDITY_STATE_TEMPLATE = "target_humidity_state_template"
CONF_TARGET_HUMIDITY_STATE_TOPIC = "target_humidity_state_topic"

DEFAULT_NAME = "MQTT Humidifier"
DEFAULT_OPTIMISTIC = False
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


def valid_mode_configuration(config):
    """Validate that the mode reset payload is not one of the available modes."""
    if config.get(CONF_PAYLOAD_RESET_MODE) in config.get(CONF_AVAILABLE_MODES_LIST):
        raise ValueError("modes must not contain payload_reset_mode")
    return config


def valid_humidity_range_configuration(config):
    """Validate that the target_humidity range configuration is valid, throws if it isn't."""
    if config.get(CONF_TARGET_HUMIDITY_MIN) >= config.get(CONF_TARGET_HUMIDITY_MAX):
        raise ValueError("target_humidity_max must be > target_humidity_min")
    if config.get(CONF_TARGET_HUMIDITY_MAX) > 100:
        raise ValueError("max_humidity must be <= 100")

    return config


_PLATFORM_SCHEMA_BASE = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    {
        # CONF_AVAIALABLE_MODES_LIST and CONF_MODE_COMMAND_TOPIC must be used together
        vol.Inclusive(
            CONF_AVAILABLE_MODES_LIST, "available_modes", default=[]
        ): cv.ensure_list,
        vol.Inclusive(
            CONF_MODE_COMMAND_TOPIC, "available_modes"
        ): mqtt.valid_publish_topic,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_DEVICE_CLASS, default=DEVICE_CLASS_HUMIDIFIER): vol.In(
            [DEVICE_CLASS_HUMIDIFIER, DEVICE_CLASS_DEHUMIDIFIER]
        ),
        vol.Optional(CONF_MODE_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_MODE_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(CONF_MODE_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_TARGET_HUMIDITY_COMMAND_TOPIC): mqtt.valid_publish_topic,
        vol.Optional(CONF_TARGET_HUMIDITY_COMMAND_TEMPLATE): cv.template,
        vol.Optional(
            CONF_TARGET_HUMIDITY_MAX, default=DEFAULT_MAX_HUMIDITY
        ): cv.positive_int,
        vol.Optional(
            CONF_TARGET_HUMIDITY_MIN, default=DEFAULT_MIN_HUMIDITY
        ): cv.positive_int,
        vol.Optional(CONF_TARGET_HUMIDITY_STATE_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY_STATE_TOPIC): mqtt.valid_subscribe_topic,
        vol.Optional(
            CONF_PAYLOAD_RESET_HUMIDITY, default=DEFAULT_PAYLOAD_RESET
        ): cv.string,
        vol.Optional(CONF_PAYLOAD_RESET_MODE, default=DEFAULT_PAYLOAD_RESET): cv.string,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE,
    valid_humidity_range_configuration,
    valid_mode_configuration,
)

DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    valid_humidity_range_configuration,
    valid_mode_configuration,
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT humidifier through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT humidifier dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, humidifier.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT humidifier."""
    async_add_entities([MqttHumidifier(hass, config, config_entry, discovery_data)])


class MqttHumidifier(MqttEntity, HumidifierEntity):
    """A MQTT humidifier component."""

    _entity_id_format = humidifier.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT humidifier."""
        self._state = False
        self._target_humidity = None
        self._mode = None
        self._supported_features = 0

        self._topic = None
        self._payload = None
        self._value_templates = None
        self._command_templates = None
        self._optimistic = None
        self._optimistic_target_humidity = None
        self._optimistic_mode = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_min_humidity = config.get(CONF_TARGET_HUMIDITY_MIN)
        self._attr_max_humidity = config.get(CONF_TARGET_HUMIDITY_MAX)

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
        self._value_templates = {
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            ATTR_HUMIDITY: config.get(CONF_TARGET_HUMIDITY_STATE_TEMPLATE),
            ATTR_MODE: config.get(CONF_MODE_STATE_TEMPLATE),
        }
        self._command_templates = {
            CONF_STATE: config.get(CONF_COMMAND_TEMPLATE),
            ATTR_HUMIDITY: config.get(CONF_TARGET_HUMIDITY_COMMAND_TEMPLATE),
            ATTR_MODE: config.get(CONF_MODE_COMMAND_TEMPLATE),
        }
        self._payload = {
            "STATE_ON": config[CONF_PAYLOAD_ON],
            "STATE_OFF": config[CONF_PAYLOAD_OFF],
            "HUMIDITY_RESET": config[CONF_PAYLOAD_RESET_HUMIDITY],
            "MODE_RESET": config[CONF_PAYLOAD_RESET_MODE],
        }
        if CONF_MODE_COMMAND_TOPIC in config and CONF_AVAILABLE_MODES_LIST in config:
            self._available_modes = config[CONF_AVAILABLE_MODES_LIST]
        else:
            self._available_modes = []
        if self._available_modes:
            self._attr_supported_features = SUPPORT_MODES
        else:
            self._attr_supported_features = 0

        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or self._topic[CONF_STATE_TOPIC] is None
        self._optimistic_target_humidity = (
            optimistic or self._topic[CONF_TARGET_HUMIDITY_STATE_TOPIC] is None
        )
        self._optimistic_mode = optimistic or self._topic[CONF_MODE_STATE_TOPIC] is None

        for tpl_dict in (self._command_templates, self._value_templates):
            for key, tpl in tpl_dict.items():
                if tpl is None:
                    tpl_dict[key] = lambda value: value
                else:
                    tpl.hass = self.hass
                    tpl_dict[key] = tpl.async_render_with_possible_json_value

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        topics = {}

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new received MQTT message."""
            payload = self._value_templates[CONF_STATE](msg.payload)
            if not payload:
                _LOGGER.debug("Ignoring empty state from '%s'", msg.topic)
                return
            if payload == self._payload["STATE_ON"]:
                self._state = True
            elif payload == self._payload["STATE_OFF"]:
                self._state = False
            self.async_write_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._topic[CONF_STATE_TOPIC],
                "msg_callback": state_received,
                "qos": self._config[CONF_QOS],
            }

        @callback
        @log_messages(self.hass, self.entity_id)
        def target_humidity_received(msg):
            """Handle new received MQTT message for the target humidity."""
            rendered_target_humidity_payload = self._value_templates[ATTR_HUMIDITY](
                msg.payload
            )
            if not rendered_target_humidity_payload:
                _LOGGER.debug("Ignoring empty target humidity from '%s'", msg.topic)
                return
            if rendered_target_humidity_payload == self._payload["HUMIDITY_RESET"]:
                self._target_humidity = None
                self.async_write_ha_state()
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
            self._target_humidity = target_humidity
            self.async_write_ha_state()

        if self._topic[CONF_TARGET_HUMIDITY_STATE_TOPIC] is not None:
            topics[CONF_TARGET_HUMIDITY_STATE_TOPIC] = {
                "topic": self._topic[CONF_TARGET_HUMIDITY_STATE_TOPIC],
                "msg_callback": target_humidity_received,
                "qos": self._config[CONF_QOS],
            }
            self._target_humidity = None

        @callback
        @log_messages(self.hass, self.entity_id)
        def mode_received(msg):
            """Handle new received MQTT message for mode."""
            mode = self._value_templates[ATTR_MODE](msg.payload)
            if mode == self._payload["MODE_RESET"]:
                self._mode = None
                self.async_write_ha_state()
                return
            if not mode:
                _LOGGER.debug("Ignoring empty mode from '%s'", msg.topic)
                return
            if mode not in self.available_modes:
                _LOGGER.warning(
                    "'%s' received on topic %s. '%s' is not a valid mode",
                    msg.payload,
                    msg.topic,
                    mode,
                )
                return

            self._mode = mode
            self.async_write_ha_state()

        if self._topic[CONF_MODE_STATE_TOPIC] is not None:
            topics[CONF_MODE_STATE_TOPIC] = {
                "topic": self._topic[CONF_MODE_STATE_TOPIC],
                "msg_callback": mode_received,
                "qos": self._config[CONF_QOS],
            }
            self._mode = None

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def available_modes(self) -> list:
        """Get the list of available modes."""
        return self._available_modes

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def target_humidity(self):
        """Return the current target humidity."""
        return self._target_humidity

    @property
    def mode(self):
        """Return the current mode."""
        return self._mode

    async def async_turn_on(
        self,
        **kwargs,
    ) -> None:
        """Turn on the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_ON"])
        await mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[CONF_STATE](self._payload["STATE_OFF"])
        await mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
        if self._optimistic:
            self._state = False
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the humidifier.

        This method is a coroutine.
        """
        mqtt_payload = self._command_templates[ATTR_HUMIDITY](humidity)
        await mqtt.async_publish(
            self.hass,
            self._topic[CONF_TARGET_HUMIDITY_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic_target_humidity:
            self._target_humidity = humidity
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan.

        This method is a coroutine.
        """
        if mode not in self.available_modes:
            _LOGGER.warning("'%s'is not a valid mode", mode)
            return

        mqtt_payload = self._command_templates[ATTR_MODE](mode)

        await mqtt.async_publish(
            self.hass,
            self._topic[CONF_MODE_COMMAND_TOPIC],
            mqtt_payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic_mode:
            self._mode = mode
            self.async_write_ha_state()
