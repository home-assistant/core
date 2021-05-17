"""Support for MQTT lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_VALUE_TEMPLATE,
    STATE_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.color as color_util

from .. import CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN, CONF_STATE_TOPIC, subscription
from ... import mqtt
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_BRIGHTNESS_COMMAND_TOPIC = "brightness_command_topic"
CONF_BRIGHTNESS_SCALE = "brightness_scale"
CONF_BRIGHTNESS_STATE_TOPIC = "brightness_state_topic"
CONF_BRIGHTNESS_VALUE_TEMPLATE = "brightness_value_template"
CONF_COLOR_TEMP_COMMAND_TEMPLATE = "color_temp_command_template"
CONF_COLOR_TEMP_COMMAND_TOPIC = "color_temp_command_topic"
CONF_COLOR_TEMP_STATE_TOPIC = "color_temp_state_topic"
CONF_COLOR_TEMP_VALUE_TEMPLATE = "color_temp_value_template"
CONF_EFFECT_COMMAND_TOPIC = "effect_command_topic"
CONF_EFFECT_LIST = "effect_list"
CONF_EFFECT_STATE_TOPIC = "effect_state_topic"
CONF_EFFECT_VALUE_TEMPLATE = "effect_value_template"
CONF_HS_COMMAND_TOPIC = "hs_command_topic"
CONF_HS_STATE_TOPIC = "hs_state_topic"
CONF_HS_VALUE_TEMPLATE = "hs_value_template"
CONF_MAX_MIREDS = "max_mireds"
CONF_MIN_MIREDS = "min_mireds"
CONF_RGB_COMMAND_TEMPLATE = "rgb_command_template"
CONF_RGB_COMMAND_TOPIC = "rgb_command_topic"
CONF_RGB_STATE_TOPIC = "rgb_state_topic"
CONF_RGB_VALUE_TEMPLATE = "rgb_value_template"
CONF_STATE_VALUE_TEMPLATE = "state_value_template"
CONF_XY_COMMAND_TOPIC = "xy_command_topic"
CONF_XY_STATE_TOPIC = "xy_state_topic"
CONF_XY_VALUE_TEMPLATE = "xy_value_template"
CONF_WHITE_VALUE_COMMAND_TOPIC = "white_value_command_topic"
CONF_WHITE_VALUE_SCALE = "white_value_scale"
CONF_WHITE_VALUE_STATE_TOPIC = "white_value_state_topic"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"
CONF_ON_COMMAND_TYPE = "on_command_type"

DEFAULT_BRIGHTNESS_SCALE = 255
DEFAULT_NAME = "MQTT LightEntity"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_WHITE_VALUE_SCALE = 255
DEFAULT_ON_COMMAND_TYPE = "last"

VALUES_ON_COMMAND_TYPE = ["first", "last", "brightness"]

COMMAND_TEMPLATE_KEYS = [CONF_COLOR_TEMP_COMMAND_TEMPLATE, CONF_RGB_COMMAND_TEMPLATE]
VALUE_TEMPLATE_KEYS = [
    CONF_BRIGHTNESS_VALUE_TEMPLATE,
    CONF_COLOR_TEMP_VALUE_TEMPLATE,
    CONF_EFFECT_VALUE_TEMPLATE,
    CONF_HS_VALUE_TEMPLATE,
    CONF_RGB_VALUE_TEMPLATE,
    CONF_STATE_VALUE_TEMPLATE,
    CONF_WHITE_VALUE_TEMPLATE,
    CONF_XY_VALUE_TEMPLATE,
]

PLATFORM_SCHEMA_BASIC = (
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_BRIGHTNESS_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(CONF_BRIGHTNESS_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_BRIGHTNESS_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_COLOR_TEMP_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_COLOR_TEMP_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_EFFECT_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_EFFECT_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_EFFECT_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_HS_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_HS_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_HS_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_ON_COMMAND_TYPE, default=DEFAULT_ON_COMMAND_TYPE): vol.In(
                VALUES_ON_COMMAND_TYPE
            ),
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
            vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
            vol.Optional(CONF_RGB_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_RGB_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_RGB_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_RGB_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_WHITE_VALUE_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(
                CONF_WHITE_VALUE_SCALE, default=DEFAULT_WHITE_VALUE_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(CONF_WHITE_VALUE_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_XY_COMMAND_TOPIC): mqtt.valid_publish_topic,
            vol.Optional(CONF_XY_STATE_TOPIC): mqtt.valid_subscribe_topic,
            vol.Optional(CONF_XY_VALUE_TEMPLATE): cv.template,
        }
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)


async def async_setup_entity_basic(
    hass, config, async_add_entities, config_entry, discovery_data=None
):
    """Set up a MQTT Light."""
    if CONF_STATE_VALUE_TEMPLATE not in config and CONF_VALUE_TEMPLATE in config:
        config[CONF_STATE_VALUE_TEMPLATE] = config[CONF_VALUE_TEMPLATE]

    async_add_entities([MqttLight(hass, config, config_entry, discovery_data)])


class MqttLight(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT light."""

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize MQTT light."""
        self._brightness = None
        self._color_temp = None
        self._effect = None
        self._hs_color = None
        self._state = False
        self._white_value = None

        self._topic = None
        self._payload = None
        self._command_templates = None
        self._value_templates = None
        self._optimistic = False
        self._optimistic_rgb_color = False
        self._optimistic_brightness = False
        self._optimistic_color_temp = False
        self._optimistic_effect = False
        self._optimistic_hs_color = False
        self._optimistic_white_value = False
        self._optimistic_xy_color = False

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA_BASIC

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        topic = {
            key: config.get(key)
            for key in (
                CONF_BRIGHTNESS_COMMAND_TOPIC,
                CONF_BRIGHTNESS_STATE_TOPIC,
                CONF_COLOR_TEMP_COMMAND_TOPIC,
                CONF_COLOR_TEMP_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_EFFECT_COMMAND_TOPIC,
                CONF_EFFECT_STATE_TOPIC,
                CONF_HS_COMMAND_TOPIC,
                CONF_HS_STATE_TOPIC,
                CONF_RGB_COMMAND_TOPIC,
                CONF_RGB_STATE_TOPIC,
                CONF_STATE_TOPIC,
                CONF_WHITE_VALUE_COMMAND_TOPIC,
                CONF_WHITE_VALUE_STATE_TOPIC,
                CONF_XY_COMMAND_TOPIC,
                CONF_XY_STATE_TOPIC,
            )
        }
        self._topic = topic
        self._payload = {"on": config[CONF_PAYLOAD_ON], "off": config[CONF_PAYLOAD_OFF]}

        value_templates = {}
        for key in VALUE_TEMPLATE_KEYS:
            value_templates[key] = lambda value, _: value
        for key in VALUE_TEMPLATE_KEYS & config.keys():
            tpl = config[key]
            value_templates[key] = tpl.async_render_with_possible_json_value
            tpl.hass = self.hass
        self._value_templates = value_templates

        command_templates = {}
        for key in COMMAND_TEMPLATE_KEYS:
            command_templates[key] = None
        for key in COMMAND_TEMPLATE_KEYS & config.keys():
            tpl = config[key]
            command_templates[key] = tpl.async_render
            tpl.hass = self.hass
        self._command_templates = command_templates

        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._optimistic_rgb_color = optimistic or topic[CONF_RGB_STATE_TOPIC] is None
        self._optimistic_brightness = (
            optimistic
            or (
                topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None
                and topic[CONF_BRIGHTNESS_STATE_TOPIC] is None
            )
            or (
                topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is None
                and topic[CONF_RGB_STATE_TOPIC] is None
            )
        )
        self._optimistic_color_temp = (
            optimistic or topic[CONF_COLOR_TEMP_STATE_TOPIC] is None
        )
        self._optimistic_effect = optimistic or topic[CONF_EFFECT_STATE_TOPIC] is None
        self._optimistic_hs_color = optimistic or topic[CONF_HS_STATE_TOPIC] is None
        self._optimistic_white_value = (
            optimistic or topic[CONF_WHITE_VALUE_STATE_TOPIC] is None
        )
        self._optimistic_xy_color = optimistic or topic[CONF_XY_STATE_TOPIC] is None

    def _is_optimistic(self, attribute):
        """Return True if the attribute is optimistically updated."""
        return getattr(self, f"_optimistic_{attribute}")

    async def _subscribe_topics(self):  # noqa: C901
        """(Re)Subscribe to topics."""
        topics = {}

        last_state = await self.async_get_last_state()

        def add_topic(topic, msg_callback):
            """Add a topic."""
            if self._topic[topic] is not None:
                topics[topic] = {
                    "topic": self._topic[topic],
                    "msg_callback": msg_callback,
                    "qos": self._config[CONF_QOS],
                }

        def restore_state(attribute, condition_attribute=None):
            """Restore a state attribute."""
            if condition_attribute is None:
                condition_attribute = attribute
            optimistic = self._is_optimistic(condition_attribute)
            if optimistic and last_state and last_state.attributes.get(attribute):
                setattr(self, f"_{attribute}", last_state.attributes[attribute])

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new MQTT messages."""
            payload = self._value_templates[CONF_STATE_VALUE_TEMPLATE](
                msg.payload, None
            )
            if not payload:
                _LOGGER.debug("Ignoring empty state message from '%s'", msg.topic)
                return

            if payload == self._payload["on"]:
                self._state = True
            elif payload == self._payload["off"]:
                self._state = False
            self.async_write_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._topic[CONF_STATE_TOPIC],
                "msg_callback": state_received,
                "qos": self._config[CONF_QOS],
            }
        elif self._optimistic and last_state:
            self._state = last_state.state == STATE_ON

        @callback
        @log_messages(self.hass, self.entity_id)
        def brightness_received(msg):
            """Handle new MQTT messages for the brightness."""
            payload = self._value_templates[CONF_BRIGHTNESS_VALUE_TEMPLATE](
                msg.payload, None
            )
            if not payload:
                _LOGGER.debug("Ignoring empty brightness message from '%s'", msg.topic)
                return

            device_value = float(payload)
            percent_bright = device_value / self._config[CONF_BRIGHTNESS_SCALE]
            self._brightness = percent_bright * 255
            self.async_write_ha_state()

        add_topic(CONF_BRIGHTNESS_STATE_TOPIC, brightness_received)
        restore_state(ATTR_BRIGHTNESS)

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgb_received(msg):
            """Handle new MQTT messages for RGB."""
            payload = self._value_templates[CONF_RGB_VALUE_TEMPLATE](msg.payload, None)
            if not payload:
                _LOGGER.debug("Ignoring empty rgb message from '%s'", msg.topic)
                return

            rgb = [int(val) for val in payload.split(",")]
            self._hs_color = color_util.color_RGB_to_hs(*rgb)
            if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is None:
                percent_bright = float(color_util.color_RGB_to_hsv(*rgb)[2]) / 100.0
                self._brightness = percent_bright * 255
            self.async_write_ha_state()

        add_topic(CONF_RGB_STATE_TOPIC, rgb_received)
        restore_state(ATTR_HS_COLOR, ATTR_RGB_COLOR)

        @callback
        @log_messages(self.hass, self.entity_id)
        def color_temp_received(msg):
            """Handle new MQTT messages for color temperature."""
            payload = self._value_templates[CONF_COLOR_TEMP_VALUE_TEMPLATE](
                msg.payload, None
            )
            if not payload:
                _LOGGER.debug("Ignoring empty color temp message from '%s'", msg.topic)
                return

            self._color_temp = int(payload)
            self.async_write_ha_state()

        add_topic(CONF_COLOR_TEMP_STATE_TOPIC, color_temp_received)
        restore_state(ATTR_COLOR_TEMP)

        @callback
        @log_messages(self.hass, self.entity_id)
        def effect_received(msg):
            """Handle new MQTT messages for effect."""
            payload = self._value_templates[CONF_EFFECT_VALUE_TEMPLATE](
                msg.payload, None
            )
            if not payload:
                _LOGGER.debug("Ignoring empty effect message from '%s'", msg.topic)
                return

            self._effect = payload
            self.async_write_ha_state()

        add_topic(CONF_EFFECT_STATE_TOPIC, effect_received)
        restore_state(ATTR_EFFECT)

        @callback
        @log_messages(self.hass, self.entity_id)
        def hs_received(msg):
            """Handle new MQTT messages for hs color."""
            payload = self._value_templates[CONF_HS_VALUE_TEMPLATE](msg.payload, None)
            if not payload:
                _LOGGER.debug("Ignoring empty hs message from '%s'", msg.topic)
                return

            try:
                hs_color = [float(val) for val in payload.split(",", 2)]
                self._hs_color = hs_color
                self.async_write_ha_state()
            except ValueError:
                _LOGGER.debug("Failed to parse hs state update: '%s'", payload)

        add_topic(CONF_HS_STATE_TOPIC, hs_received)
        restore_state(ATTR_HS_COLOR)

        @callback
        @log_messages(self.hass, self.entity_id)
        def white_value_received(msg):
            """Handle new MQTT messages for white value."""
            payload = self._value_templates[CONF_WHITE_VALUE_TEMPLATE](
                msg.payload, None
            )
            if not payload:
                _LOGGER.debug("Ignoring empty white value message from '%s'", msg.topic)
                return

            device_value = float(payload)
            percent_white = device_value / self._config[CONF_WHITE_VALUE_SCALE]
            self._white_value = percent_white * 255
            self.async_write_ha_state()

        add_topic(CONF_WHITE_VALUE_STATE_TOPIC, white_value_received)
        restore_state(ATTR_WHITE_VALUE)

        @callback
        @log_messages(self.hass, self.entity_id)
        def xy_received(msg):
            """Handle new MQTT messages for xy color."""
            payload = self._value_templates[CONF_XY_VALUE_TEMPLATE](msg.payload, None)
            if not payload:
                _LOGGER.debug("Ignoring empty xy-color message from '%s'", msg.topic)
                return

            xy_color = [float(val) for val in payload.split(",")]
            self._hs_color = color_util.color_xy_to_hs(*xy_color)
            self.async_write_ha_state()

        add_topic(CONF_XY_STATE_TOPIC, xy_received)
        restore_state(ATTR_HS_COLOR, ATTR_XY_COLOR)

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        brightness = self._brightness
        if brightness:
            brightness = min(round(brightness), 255)
        return brightness

    @property
    def hs_color(self):
        """Return the hs color value."""
        if self._white_value:
            return None
        return self._hs_color

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        supports_color = (
            self._topic[CONF_RGB_COMMAND_TOPIC]
            or self._topic[CONF_HS_COMMAND_TOPIC]
            or self._topic[CONF_XY_COMMAND_TOPIC]
        )
        if self._white_value or not supports_color:
            return self._color_temp
        return None

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._config.get(CONF_MIN_MIREDS, super().min_mireds)

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._config.get(CONF_MAX_MIREDS, super().max_mireds)

    @property
    def white_value(self):
        """Return the white property."""
        white_value = self._white_value
        if white_value:
            white_value = min(round(white_value), 255)
            return white_value
        return None

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._config.get(CONF_EFFECT_LIST)

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        supported_features |= self._topic[CONF_RGB_COMMAND_TOPIC] is not None and (
            SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        )
        supported_features |= (
            self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None
            and SUPPORT_BRIGHTNESS
        )
        supported_features |= (
            self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None
            and SUPPORT_COLOR_TEMP
        )
        supported_features |= (
            self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None and SUPPORT_EFFECT
        )
        supported_features |= (
            self._topic[CONF_HS_COMMAND_TOPIC] is not None and SUPPORT_COLOR
        )
        supported_features |= (
            self._topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None
            and SUPPORT_WHITE_VALUE
        )
        supported_features |= (
            self._topic[CONF_XY_COMMAND_TOPIC] is not None and SUPPORT_COLOR
        )

        return supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False
        on_command_type = self._config[CONF_ON_COMMAND_TYPE]

        def publish(topic, payload):
            """Publish an MQTT message."""
            mqtt.async_publish(
                self.hass,
                self._topic[topic],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
            )

        def set_optimistic(attribute, value, condition_attribute=None):
            """Optimistically update a state attribute."""
            if condition_attribute is None:
                condition_attribute = attribute
            if not self._is_optimistic(condition_attribute):
                return False
            setattr(self, f"_{attribute}", value)
            return True

        if on_command_type == "first":
            publish(CONF_COMMAND_TOPIC, self._payload["on"])
            should_update = True

        # If brightness is being used instead of an on command, make sure
        # there is a brightness input.  Either set the brightness to our
        # saved value or the maximum value if this is the first call
        elif on_command_type == "brightness" and ATTR_BRIGHTNESS not in kwargs:
            kwargs[ATTR_BRIGHTNESS] = self._brightness if self._brightness else 255

        if ATTR_HS_COLOR in kwargs and self._topic[CONF_RGB_COMMAND_TOPIC] is not None:

            hs_color = kwargs[ATTR_HS_COLOR]

            # If there's a brightness topic set, we don't want to scale the RGB
            # values given using the brightness.
            if self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
                brightness = 255
            else:
                brightness = kwargs.get(
                    ATTR_BRIGHTNESS, self._brightness if self._brightness else 255
                )
            rgb = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], brightness / 255 * 100
            )
            tpl = self._command_templates[CONF_RGB_COMMAND_TEMPLATE]
            if tpl:
                rgb_color_str = tpl({"red": rgb[0], "green": rgb[1], "blue": rgb[2]})
            else:
                rgb_color_str = f"{rgb[0]},{rgb[1]},{rgb[2]}"

            publish(CONF_RGB_COMMAND_TOPIC, rgb_color_str)
            should_update |= set_optimistic(ATTR_HS_COLOR, hs_color, ATTR_RGB_COLOR)

        if ATTR_HS_COLOR in kwargs and self._topic[CONF_HS_COMMAND_TOPIC] is not None:
            hs_color = kwargs[ATTR_HS_COLOR]
            publish(CONF_HS_COMMAND_TOPIC, f"{hs_color[0]},{hs_color[1]}")
            should_update |= set_optimistic(ATTR_HS_COLOR, hs_color)

        if ATTR_HS_COLOR in kwargs and self._topic[CONF_XY_COMMAND_TOPIC] is not None:

            xy_color = color_util.color_hs_to_xy(*kwargs[ATTR_HS_COLOR])
            publish(CONF_XY_COMMAND_TOPIC, f"{xy_color[0]},{xy_color[1]}")
            should_update |= set_optimistic(ATTR_HS_COLOR, hs_color, ATTR_XY_COLOR)

        if (
            ATTR_BRIGHTNESS in kwargs
            and self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None
        ):
            brightness_normalized = kwargs[ATTR_BRIGHTNESS] / 255
            brightness_scale = self._config[CONF_BRIGHTNESS_SCALE]
            device_brightness = min(
                round(brightness_normalized * brightness_scale), brightness_scale
            )
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)
            publish(CONF_BRIGHTNESS_COMMAND_TOPIC, device_brightness)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_HS_COLOR not in kwargs
            and self._topic[CONF_RGB_COMMAND_TOPIC] is not None
        ):
            hs_color = self._hs_color if self._hs_color is not None else (0, 0)
            rgb = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], kwargs[ATTR_BRIGHTNESS] / 255 * 100
            )
            tpl = self._command_templates[CONF_RGB_COMMAND_TEMPLATE]
            if tpl:
                rgb_color_str = tpl({"red": rgb[0], "green": rgb[1], "blue": rgb[2]})
            else:
                rgb_color_str = f"{rgb[0]},{rgb[1]},{rgb[2]}"

            publish(CONF_RGB_COMMAND_TOPIC, rgb_color_str)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])

        if (
            ATTR_COLOR_TEMP in kwargs
            and self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None
        ):
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            tpl = self._command_templates[CONF_COLOR_TEMP_COMMAND_TEMPLATE]

            if tpl:
                color_temp = tpl({"value": color_temp})

            publish(CONF_COLOR_TEMP_COMMAND_TOPIC, color_temp)
            should_update |= set_optimistic(ATTR_COLOR_TEMP, kwargs[ATTR_COLOR_TEMP])

        if ATTR_EFFECT in kwargs and self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None:
            effect = kwargs[ATTR_EFFECT]
            if effect in self._config.get(CONF_EFFECT_LIST):
                publish(CONF_EFFECT_COMMAND_TOPIC, effect)
                should_update |= set_optimistic(ATTR_EFFECT, effect)

        if (
            ATTR_WHITE_VALUE in kwargs
            and self._topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None
        ):
            percent_white = float(kwargs[ATTR_WHITE_VALUE]) / 255
            white_scale = self._config[CONF_WHITE_VALUE_SCALE]
            device_white_value = min(round(percent_white * white_scale), white_scale)
            publish(CONF_WHITE_VALUE_COMMAND_TOPIC, device_white_value)
            should_update |= set_optimistic(ATTR_WHITE_VALUE, kwargs[ATTR_WHITE_VALUE])

        if on_command_type == "last":
            publish(CONF_COMMAND_TOPIC, self._payload["on"])
            should_update = True

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._topic[CONF_COMMAND_TOPIC],
            self._payload["off"],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = False
            self.async_write_ha_state()
