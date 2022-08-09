"""Support for MQTT lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_WHITE,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
    ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_WHITE_VALUE,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    valid_supported_color_modes,
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

from .. import subscription
from ..config import MQTT_RW_SCHEMA
from ..const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_STATE_VALUE_TEMPLATE,
    PAYLOAD_NONE,
)
from ..debug_info import log_messages
from ..mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity
from ..models import MqttCommandTemplate, MqttValueTemplate
from ..util import valid_publish_topic, valid_subscribe_topic
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_BRIGHTNESS_COMMAND_TEMPLATE = "brightness_command_template"
CONF_BRIGHTNESS_COMMAND_TOPIC = "brightness_command_topic"
CONF_BRIGHTNESS_SCALE = "brightness_scale"
CONF_BRIGHTNESS_STATE_TOPIC = "brightness_state_topic"
CONF_BRIGHTNESS_VALUE_TEMPLATE = "brightness_value_template"
CONF_COLOR_MODE_STATE_TOPIC = "color_mode_state_topic"
CONF_COLOR_MODE_VALUE_TEMPLATE = "color_mode_value_template"
CONF_COLOR_TEMP_COMMAND_TEMPLATE = "color_temp_command_template"
CONF_COLOR_TEMP_COMMAND_TOPIC = "color_temp_command_topic"
CONF_COLOR_TEMP_STATE_TOPIC = "color_temp_state_topic"
CONF_COLOR_TEMP_VALUE_TEMPLATE = "color_temp_value_template"
CONF_EFFECT_COMMAND_TEMPLATE = "effect_command_template"
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
CONF_RGBW_COMMAND_TEMPLATE = "rgbw_command_template"
CONF_RGBW_COMMAND_TOPIC = "rgbw_command_topic"
CONF_RGBW_STATE_TOPIC = "rgbw_state_topic"
CONF_RGBW_VALUE_TEMPLATE = "rgbw_value_template"
CONF_RGBWW_COMMAND_TEMPLATE = "rgbww_command_template"
CONF_RGBWW_COMMAND_TOPIC = "rgbww_command_topic"
CONF_RGBWW_STATE_TOPIC = "rgbww_state_topic"
CONF_RGBWW_VALUE_TEMPLATE = "rgbww_value_template"
CONF_XY_COMMAND_TOPIC = "xy_command_topic"
CONF_XY_STATE_TOPIC = "xy_state_topic"
CONF_XY_VALUE_TEMPLATE = "xy_value_template"
CONF_WHITE_COMMAND_TOPIC = "white_command_topic"
CONF_WHITE_SCALE = "white_scale"
CONF_WHITE_VALUE_COMMAND_TOPIC = "white_value_command_topic"
CONF_WHITE_VALUE_SCALE = "white_value_scale"
CONF_WHITE_VALUE_STATE_TOPIC = "white_value_state_topic"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"
CONF_ON_COMMAND_TYPE = "on_command_type"

MQTT_LIGHT_ATTRIBUTES_BLOCKED = frozenset(
    {
        ATTR_COLOR_MODE,
        ATTR_BRIGHTNESS,
        ATTR_COLOR_TEMP,
        ATTR_EFFECT,
        ATTR_EFFECT_LIST,
        ATTR_HS_COLOR,
        ATTR_MAX_MIREDS,
        ATTR_MIN_MIREDS,
        ATTR_RGB_COLOR,
        ATTR_RGBW_COLOR,
        ATTR_RGBWW_COLOR,
        ATTR_SUPPORTED_COLOR_MODES,
        ATTR_WHITE_VALUE,
        ATTR_XY_COLOR,
    }
)

DEFAULT_BRIGHTNESS_SCALE = 255
DEFAULT_NAME = "MQTT LightEntity"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_WHITE_VALUE_SCALE = 255
DEFAULT_WHITE_SCALE = 255
DEFAULT_ON_COMMAND_TYPE = "last"

VALUES_ON_COMMAND_TYPE = ["first", "last", "brightness"]

COMMAND_TEMPLATE_KEYS = [
    CONF_BRIGHTNESS_COMMAND_TEMPLATE,
    CONF_COLOR_TEMP_COMMAND_TEMPLATE,
    CONF_EFFECT_COMMAND_TEMPLATE,
    CONF_RGB_COMMAND_TEMPLATE,
    CONF_RGBW_COMMAND_TEMPLATE,
    CONF_RGBWW_COMMAND_TEMPLATE,
]
VALUE_TEMPLATE_KEYS = [
    CONF_BRIGHTNESS_VALUE_TEMPLATE,
    CONF_COLOR_MODE_VALUE_TEMPLATE,
    CONF_COLOR_TEMP_VALUE_TEMPLATE,
    CONF_EFFECT_VALUE_TEMPLATE,
    CONF_HS_VALUE_TEMPLATE,
    CONF_RGB_VALUE_TEMPLATE,
    CONF_RGBW_VALUE_TEMPLATE,
    CONF_RGBWW_VALUE_TEMPLATE,
    CONF_STATE_VALUE_TEMPLATE,
    CONF_WHITE_VALUE_TEMPLATE,
    CONF_XY_VALUE_TEMPLATE,
]

_PLATFORM_SCHEMA_BASE = (
    MQTT_RW_SCHEMA.extend(
        {
            vol.Optional(CONF_BRIGHTNESS_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_BRIGHTNESS_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(
                CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(CONF_BRIGHTNESS_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_BRIGHTNESS_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_MODE_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_COLOR_MODE_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_COLOR_TEMP_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_COLOR_TEMP_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_EFFECT_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_EFFECT_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_EFFECT_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_EFFECT_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_HS_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_HS_STATE_TOPIC): valid_subscribe_topic,
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
            vol.Optional(CONF_RGB_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_RGB_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_RGB_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_RGBW_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_RGBW_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_RGBW_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_RGBW_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_RGBWW_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_RGBWW_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_RGBWW_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_RGBWW_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_WHITE_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_WHITE_SCALE, default=DEFAULT_WHITE_SCALE): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
            vol.Optional(CONF_WHITE_VALUE_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(
                CONF_WHITE_VALUE_SCALE, default=DEFAULT_WHITE_VALUE_SCALE
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(CONF_WHITE_VALUE_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_XY_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_XY_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_XY_VALUE_TEMPLATE): cv.template,
        },
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

# The use of PLATFORM_SCHEMA is deprecated in HA Core 2022.6
PLATFORM_SCHEMA_BASIC = vol.All(
    # CONF_WHITE_VALUE_* is deprecated, support will be removed in release 2022.9
    cv.deprecated(CONF_WHITE_VALUE_COMMAND_TOPIC),
    cv.deprecated(CONF_WHITE_VALUE_SCALE),
    cv.deprecated(CONF_WHITE_VALUE_STATE_TOPIC),
    cv.deprecated(CONF_WHITE_VALUE_TEMPLATE),
    cv.PLATFORM_SCHEMA.extend(_PLATFORM_SCHEMA_BASE.schema),
)

DISCOVERY_SCHEMA_BASIC = vol.All(
    # CONF_VALUE_TEMPLATE is no longer supported, support was removed in 2022.2
    cv.removed(CONF_VALUE_TEMPLATE),
    # CONF_WHITE_VALUE_* is deprecated, support will be removed in release 2022.9
    cv.deprecated(CONF_WHITE_VALUE_COMMAND_TOPIC),
    cv.deprecated(CONF_WHITE_VALUE_SCALE),
    cv.deprecated(CONF_WHITE_VALUE_STATE_TOPIC),
    cv.deprecated(CONF_WHITE_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)

PLATFORM_SCHEMA_MODERN_BASIC = _PLATFORM_SCHEMA_BASE


async def async_setup_entity_basic(
    hass, config, async_add_entities, config_entry, discovery_data=None
):
    """Set up a MQTT Light."""
    async_add_entities([MqttLight(hass, config, config_entry, discovery_data)])


class MqttLight(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT light."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize MQTT light."""
        self._brightness = None
        self._color_mode = None
        self._color_temp = None
        self._effect = None
        self._hs_color = None
        self._legacy_mode = False
        self._rgb_color = None
        self._rgbw_color = None
        self._rgbww_color = None
        self._state = None
        self._supported_color_modes = None
        self._white_value = None
        self._xy_color = None

        self._topic = None
        self._payload = None
        self._command_templates = None
        self._value_templates = None
        self._optimistic = False
        self._optimistic_brightness = False
        self._optimistic_color_mode = False
        self._optimistic_color_temp = False
        self._optimistic_effect = False
        self._optimistic_hs_color = False
        self._optimistic_rgb_color = False
        self._optimistic_rgbw_color = False
        self._optimistic_rgbww_color = False
        self._optimistic_white_value = False
        self._optimistic_xy_color = False

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA_BASIC

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        if CONF_STATE_VALUE_TEMPLATE not in config and CONF_VALUE_TEMPLATE in config:
            config[CONF_STATE_VALUE_TEMPLATE] = config[CONF_VALUE_TEMPLATE]

        topic = {
            key: config.get(key)
            for key in (
                CONF_BRIGHTNESS_COMMAND_TOPIC,
                CONF_BRIGHTNESS_STATE_TOPIC,
                CONF_COLOR_MODE_STATE_TOPIC,
                CONF_COLOR_TEMP_COMMAND_TOPIC,
                CONF_COLOR_TEMP_STATE_TOPIC,
                CONF_COMMAND_TOPIC,
                CONF_EFFECT_COMMAND_TOPIC,
                CONF_EFFECT_STATE_TOPIC,
                CONF_HS_COMMAND_TOPIC,
                CONF_HS_STATE_TOPIC,
                CONF_RGB_COMMAND_TOPIC,
                CONF_RGB_STATE_TOPIC,
                CONF_RGBW_COMMAND_TOPIC,
                CONF_RGBW_STATE_TOPIC,
                CONF_RGBWW_COMMAND_TOPIC,
                CONF_RGBWW_STATE_TOPIC,
                CONF_STATE_TOPIC,
                CONF_WHITE_COMMAND_TOPIC,
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
            value_templates[key] = None
        if CONF_VALUE_TEMPLATE in config:
            value_templates = {
                key: config.get(CONF_VALUE_TEMPLATE) for key in VALUE_TEMPLATE_KEYS
            }
        for key in VALUE_TEMPLATE_KEYS & config.keys():
            value_templates[key] = config[key]
        self._value_templates = {
            key: MqttValueTemplate(
                template, entity=self
            ).async_render_with_possible_json_value
            for key, template in value_templates.items()
        }

        command_templates = {}
        for key in COMMAND_TEMPLATE_KEYS:
            command_templates[key] = None
        for key in COMMAND_TEMPLATE_KEYS & config.keys():
            command_templates[key] = MqttCommandTemplate(
                config[key], entity=self
            ).async_render
        self._command_templates = command_templates

        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic_color_mode = (
            optimistic or topic[CONF_COLOR_MODE_STATE_TOPIC] is None
        )
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._optimistic_rgb_color = optimistic or topic[CONF_RGB_STATE_TOPIC] is None
        self._optimistic_rgbw_color = optimistic or topic[CONF_RGBW_STATE_TOPIC] is None
        self._optimistic_rgbww_color = (
            optimistic or topic[CONF_RGBWW_STATE_TOPIC] is None
        )
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
        supported_color_modes = set()
        if topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._color_mode = ColorMode.COLOR_TEMP
        if topic[CONF_HS_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.HS)
            self._color_mode = ColorMode.HS
        if topic[CONF_RGB_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.RGB)
            self._color_mode = ColorMode.RGB
        if topic[CONF_RGBW_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.RGBW)
            self._color_mode = ColorMode.RGBW
        if topic[CONF_RGBWW_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.RGBWW)
            self._color_mode = ColorMode.RGBWW
        if topic[CONF_WHITE_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.WHITE)
        if topic[CONF_XY_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.XY)
            self._color_mode = ColorMode.XY
        if len(supported_color_modes) > 1:
            self._color_mode = ColorMode.UNKNOWN

        if not supported_color_modes:
            if topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
                self._color_mode = ColorMode.BRIGHTNESS
                supported_color_modes.add(ColorMode.BRIGHTNESS)
            else:
                self._color_mode = ColorMode.ONOFF
                supported_color_modes.add(ColorMode.ONOFF)

        # Validate the color_modes configuration
        self._supported_color_modes = valid_supported_color_modes(supported_color_modes)

        if topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None:
            self._legacy_mode = True

    def _is_optimistic(self, attribute):
        """Return True if the attribute is optimistically updated."""
        return getattr(self, f"_optimistic_{attribute}")

    def _prepare_subscribe_topics(self):  # noqa: C901
        """(Re)Subscribe to topics."""
        topics = {}

        def add_topic(topic, msg_callback):
            """Add a topic."""
            if self._topic[topic] is not None:
                topics[topic] = {
                    "topic": self._topic[topic],
                    "msg_callback": msg_callback,
                    "qos": self._config[CONF_QOS],
                    "encoding": self._config[CONF_ENCODING] or None,
                }

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new MQTT messages."""
            payload = self._value_templates[CONF_STATE_VALUE_TEMPLATE](msg.payload)
            if not payload:
                _LOGGER.debug("Ignoring empty state message from '%s'", msg.topic)
                return

            if payload == self._payload["on"]:
                self._state = True
            elif payload == self._payload["off"]:
                self._state = False
            elif payload == PAYLOAD_NONE:
                self._state = None
            self.async_write_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            topics[CONF_STATE_TOPIC] = {
                "topic": self._topic[CONF_STATE_TOPIC],
                "msg_callback": state_received,
                "qos": self._config[CONF_QOS],
                "encoding": self._config[CONF_ENCODING] or None,
            }

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

        def _rgbx_received(msg, template, color_mode, convert_color):
            """Handle new MQTT messages for RGBW and RGBWW."""
            payload = self._value_templates[template](msg.payload, None)
            if not payload:
                _LOGGER.debug(
                    "Ignoring empty %s message from '%s'", color_mode, msg.topic
                )
                return None
            color = tuple(int(val) for val in payload.split(","))
            if self._optimistic_color_mode:
                self._color_mode = color_mode
            if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is None:
                rgb = convert_color(*color)
                percent_bright = float(color_util.color_RGB_to_hsv(*rgb)[2]) / 100.0
                self._brightness = percent_bright * 255
            return color

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgb_received(msg):
            """Handle new MQTT messages for RGB."""
            rgb = _rgbx_received(
                msg, CONF_RGB_VALUE_TEMPLATE, ColorMode.RGB, lambda *x: x
            )
            if not rgb:
                return
            if self._legacy_mode:
                self._hs_color = color_util.color_RGB_to_hs(*rgb)
            else:
                self._rgb_color = rgb
            self.async_write_ha_state()

        add_topic(CONF_RGB_STATE_TOPIC, rgb_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgbw_received(msg):
            """Handle new MQTT messages for RGBW."""
            rgbw = _rgbx_received(
                msg,
                CONF_RGBW_VALUE_TEMPLATE,
                ColorMode.RGBW,
                color_util.color_rgbw_to_rgb,
            )
            if not rgbw:
                return
            self._rgbw_color = rgbw
            self.async_write_ha_state()

        add_topic(CONF_RGBW_STATE_TOPIC, rgbw_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgbww_received(msg):
            """Handle new MQTT messages for RGBWW."""
            rgbww = _rgbx_received(
                msg,
                CONF_RGBWW_VALUE_TEMPLATE,
                ColorMode.RGBWW,
                color_util.color_rgbww_to_rgb,
            )
            if not rgbww:
                return
            self._rgbww_color = rgbww
            self.async_write_ha_state()

        add_topic(CONF_RGBWW_STATE_TOPIC, rgbww_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def color_mode_received(msg):
            """Handle new MQTT messages for color mode."""
            payload = self._value_templates[CONF_COLOR_MODE_VALUE_TEMPLATE](
                msg.payload, None
            )
            if not payload:
                _LOGGER.debug("Ignoring empty color mode message from '%s'", msg.topic)
                return

            self._color_mode = payload
            self.async_write_ha_state()

        add_topic(CONF_COLOR_MODE_STATE_TOPIC, color_mode_received)

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

            if self._optimistic_color_mode:
                self._color_mode = ColorMode.COLOR_TEMP
            self._color_temp = int(payload)
            self.async_write_ha_state()

        add_topic(CONF_COLOR_TEMP_STATE_TOPIC, color_temp_received)

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

        @callback
        @log_messages(self.hass, self.entity_id)
        def hs_received(msg):
            """Handle new MQTT messages for hs color."""
            payload = self._value_templates[CONF_HS_VALUE_TEMPLATE](msg.payload, None)
            if not payload:
                _LOGGER.debug("Ignoring empty hs message from '%s'", msg.topic)
                return
            try:
                hs_color = tuple(float(val) for val in payload.split(",", 2))
                if self._optimistic_color_mode:
                    self._color_mode = ColorMode.HS
                self._hs_color = hs_color
                self.async_write_ha_state()
            except ValueError:
                _LOGGER.debug("Failed to parse hs state update: '%s'", payload)

        add_topic(CONF_HS_STATE_TOPIC, hs_received)

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

        @callback
        @log_messages(self.hass, self.entity_id)
        def xy_received(msg):
            """Handle new MQTT messages for xy color."""
            payload = self._value_templates[CONF_XY_VALUE_TEMPLATE](msg.payload, None)
            if not payload:
                _LOGGER.debug("Ignoring empty xy-color message from '%s'", msg.topic)
                return

            xy_color = tuple(float(val) for val in payload.split(","))
            if self._optimistic_color_mode:
                self._color_mode = ColorMode.XY
            if self._legacy_mode:
                self._hs_color = color_util.color_xy_to_hs(*xy_color)
            else:
                self._xy_color = xy_color
            self.async_write_ha_state()

        add_topic(CONF_XY_STATE_TOPIC, xy_received)

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)
        last_state = await self.async_get_last_state()

        def restore_state(attribute, condition_attribute=None):
            """Restore a state attribute."""
            if condition_attribute is None:
                condition_attribute = attribute
            optimistic = self._is_optimistic(condition_attribute)
            if optimistic and last_state and last_state.attributes.get(attribute):
                setattr(self, f"_{attribute}", last_state.attributes[attribute])

        if self._topic[CONF_STATE_TOPIC] is None and self._optimistic and last_state:
            self._state = last_state.state == STATE_ON
        restore_state(ATTR_BRIGHTNESS)
        restore_state(ATTR_RGB_COLOR)
        restore_state(ATTR_HS_COLOR, ATTR_RGB_COLOR)
        restore_state(ATTR_RGBW_COLOR)
        restore_state(ATTR_RGBWW_COLOR)
        restore_state(ATTR_COLOR_MODE)
        restore_state(ATTR_COLOR_TEMP)
        restore_state(ATTR_EFFECT)
        restore_state(ATTR_HS_COLOR)
        restore_state(ATTR_WHITE_VALUE)
        restore_state(ATTR_XY_COLOR)
        restore_state(ATTR_HS_COLOR, ATTR_XY_COLOR)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if brightness := self._brightness:
            brightness = min(round(brightness), 255)
        return brightness

    @property
    def color_mode(self):
        """Return current color mode."""
        if self._legacy_mode:
            return None
        return self._color_mode

    @property
    def hs_color(self):
        """Return the hs color value."""
        if not self._legacy_mode:
            return self._hs_color

        # Legacy mode, gate color_temp with white_value == 0
        if self._white_value:
            return None
        return self._hs_color

    @property
    def rgb_color(self):
        """Return the rgb color value."""
        return self._rgb_color

    @property
    def rgbw_color(self):
        """Return the rgbw color value."""
        return self._rgbw_color

    @property
    def rgbww_color(self):
        """Return the rgbww color value."""
        return self._rgbww_color

    @property
    def xy_color(self):
        """Return the xy color value."""
        return self._xy_color

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        if not self._legacy_mode:
            return self._color_temp

        # Legacy mode, gate color_temp with white_value > 0
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
        if white_value := self._white_value:
            return min(round(white_value), 255)
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
    def supported_color_modes(self):
        """Flag supported color modes."""
        if self._legacy_mode:
            return None
        return self._supported_color_modes

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        supported_features |= (
            self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None
            and LightEntityFeature.EFFECT
        )
        if not self._legacy_mode:
            return supported_features

        # Legacy mode
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

    async def async_turn_on(self, **kwargs):  # noqa: C901
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False
        on_command_type = self._config[CONF_ON_COMMAND_TYPE]

        async def publish(topic, payload):
            """Publish an MQTT message."""
            await self.async_publish(
                self._topic[topic],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

        def scale_rgbx(color, brightness=None):
            """Scale RGBx for brightness."""
            if brightness is None:
                # If there's a brightness topic set, we don't want to scale the RGBx
                # values given using the brightness.
                if self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
                    brightness = 255
                else:
                    brightness = kwargs.get(
                        ATTR_BRIGHTNESS, self._brightness if self._brightness else 255
                    )
            return tuple(int(channel * brightness / 255) for channel in color)

        def render_rgbx(color, template, color_mode):
            """Render RGBx payload."""
            if tpl := self._command_templates[template]:
                keys = ["red", "green", "blue"]
                if color_mode == ColorMode.RGBW:
                    keys.append("white")
                elif color_mode == ColorMode.RGBWW:
                    keys.extend(["cold_white", "warm_white"])
                rgb_color_str = tpl(variables=zip(keys, color))
            else:
                rgb_color_str = ",".join(str(channel) for channel in color)
            return rgb_color_str

        def set_optimistic(attribute, value, color_mode=None, condition_attribute=None):
            """Optimistically update a state attribute."""
            if condition_attribute is None:
                condition_attribute = attribute
            if not self._is_optimistic(condition_attribute):
                return False
            if color_mode and self._optimistic_color_mode:
                self._color_mode = color_mode
            setattr(self, f"_{attribute}", value)
            return True

        if on_command_type == "first":
            await publish(CONF_COMMAND_TOPIC, self._payload["on"])
            should_update = True

        # If brightness is being used instead of an on command, make sure
        # there is a brightness input.  Either set the brightness to our
        # saved value or the maximum value if this is the first call
        elif (
            on_command_type == "brightness"
            and ATTR_BRIGHTNESS not in kwargs
            and ATTR_WHITE not in kwargs
        ):
            kwargs[ATTR_BRIGHTNESS] = self._brightness if self._brightness else 255

        hs_color = kwargs.get(ATTR_HS_COLOR)
        if (
            hs_color
            and self._topic[CONF_RGB_COMMAND_TOPIC] is not None
            and self._legacy_mode
        ):
            # Legacy mode: Convert HS to RGB
            rgb = scale_rgbx(color_util.color_hsv_to_RGB(*hs_color, 100))
            rgb_s = render_rgbx(rgb, CONF_RGB_COMMAND_TEMPLATE, ColorMode.RGB)
            await publish(CONF_RGB_COMMAND_TOPIC, rgb_s)
            should_update |= set_optimistic(
                ATTR_HS_COLOR, hs_color, condition_attribute=ATTR_RGB_COLOR
            )

        if hs_color and self._topic[CONF_HS_COMMAND_TOPIC] is not None:
            await publish(CONF_HS_COMMAND_TOPIC, f"{hs_color[0]},{hs_color[1]}")
            should_update |= set_optimistic(ATTR_HS_COLOR, hs_color, ColorMode.HS)

        if (
            hs_color
            and self._topic[CONF_XY_COMMAND_TOPIC] is not None
            and self._legacy_mode
        ):
            # Legacy mode: Convert HS to XY
            xy_color = color_util.color_hs_to_xy(*hs_color)
            await publish(CONF_XY_COMMAND_TOPIC, f"{xy_color[0]},{xy_color[1]}")
            should_update |= set_optimistic(
                ATTR_HS_COLOR, hs_color, condition_attribute=ATTR_XY_COLOR
            )

        if (
            (rgb := kwargs.get(ATTR_RGB_COLOR))
            and self._topic[CONF_RGB_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            scaled = scale_rgbx(rgb)
            rgb_s = render_rgbx(scaled, CONF_RGB_COMMAND_TEMPLATE, ColorMode.RGB)
            await publish(CONF_RGB_COMMAND_TOPIC, rgb_s)
            should_update |= set_optimistic(ATTR_RGB_COLOR, rgb, ColorMode.RGB)

        if (
            (rgbw := kwargs.get(ATTR_RGBW_COLOR))
            and self._topic[CONF_RGBW_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            scaled = scale_rgbx(rgbw)
            rgbw_s = render_rgbx(scaled, CONF_RGBW_COMMAND_TEMPLATE, ColorMode.RGBW)
            await publish(CONF_RGBW_COMMAND_TOPIC, rgbw_s)
            should_update |= set_optimistic(ATTR_RGBW_COLOR, rgbw, ColorMode.RGBW)

        if (
            (rgbww := kwargs.get(ATTR_RGBWW_COLOR))
            and self._topic[CONF_RGBWW_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            scaled = scale_rgbx(rgbww)
            rgbww_s = render_rgbx(scaled, CONF_RGBWW_COMMAND_TEMPLATE, ColorMode.RGBWW)
            await publish(CONF_RGBWW_COMMAND_TOPIC, rgbww_s)
            should_update |= set_optimistic(ATTR_RGBWW_COLOR, rgbww, ColorMode.RGBWW)

        if (
            (xy_color := kwargs.get(ATTR_XY_COLOR))
            and self._topic[CONF_XY_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            await publish(CONF_XY_COMMAND_TOPIC, f"{xy_color[0]},{xy_color[1]}")
            should_update |= set_optimistic(ATTR_XY_COLOR, xy_color, ColorMode.XY)

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
            if tpl := self._command_templates[CONF_BRIGHTNESS_COMMAND_TEMPLATE]:
                device_brightness = tpl(variables={"value": device_brightness})
            await publish(CONF_BRIGHTNESS_COMMAND_TOPIC, device_brightness)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_HS_COLOR not in kwargs
            and self._topic[CONF_RGB_COMMAND_TOPIC] is not None
            and self._legacy_mode
        ):
            # Legacy mode
            hs_color = self._hs_color if self._hs_color is not None else (0, 0)
            brightness = kwargs[ATTR_BRIGHTNESS]
            rgb = scale_rgbx(color_util.color_hsv_to_RGB(*hs_color, 100), brightness)
            rgb_s = render_rgbx(rgb, CONF_RGB_COMMAND_TEMPLATE, ColorMode.RGB)
            await publish(CONF_RGB_COMMAND_TOPIC, rgb_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_RGB_COLOR not in kwargs
            and self._topic[CONF_RGB_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            rgb_color = self._rgb_color if self._rgb_color is not None else (255,) * 3
            rgb = scale_rgbx(rgb_color, kwargs[ATTR_BRIGHTNESS])
            rgb_s = render_rgbx(rgb, CONF_RGB_COMMAND_TEMPLATE, ColorMode.RGB)
            await publish(CONF_RGB_COMMAND_TOPIC, rgb_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_RGBW_COLOR not in kwargs
            and self._topic[CONF_RGBW_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            rgbw_color = (
                self._rgbw_color if self._rgbw_color is not None else (255,) * 4
            )
            rgbw = scale_rgbx(rgbw_color, kwargs[ATTR_BRIGHTNESS])
            rgbw_s = render_rgbx(rgbw, CONF_RGBW_COMMAND_TEMPLATE, ColorMode.RGBW)
            await publish(CONF_RGBW_COMMAND_TOPIC, rgbw_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_RGBWW_COLOR not in kwargs
            and self._topic[CONF_RGBWW_COMMAND_TOPIC] is not None
            and not self._legacy_mode
        ):
            rgbww_color = (
                self._rgbww_color if self._rgbww_color is not None else (255,) * 5
            )
            rgbww = scale_rgbx(rgbww_color, kwargs[ATTR_BRIGHTNESS])
            rgbww_s = render_rgbx(rgbww, CONF_RGBWW_COMMAND_TEMPLATE, ColorMode.RGBWW)
            await publish(CONF_RGBWW_COMMAND_TOPIC, rgbww_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        if (
            ATTR_COLOR_TEMP in kwargs
            and self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None
        ):
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            if tpl := self._command_templates[CONF_COLOR_TEMP_COMMAND_TEMPLATE]:
                color_temp = tpl(variables={"value": color_temp})

            await publish(CONF_COLOR_TEMP_COMMAND_TOPIC, color_temp)
            should_update |= set_optimistic(
                ATTR_COLOR_TEMP, kwargs[ATTR_COLOR_TEMP], ColorMode.COLOR_TEMP
            )

        if ATTR_EFFECT in kwargs and self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None:
            effect = kwargs[ATTR_EFFECT]
            if effect in self._config.get(CONF_EFFECT_LIST):
                if tpl := self._command_templates[CONF_EFFECT_COMMAND_TEMPLATE]:
                    effect = tpl(variables={"value": effect})
                await publish(CONF_EFFECT_COMMAND_TOPIC, effect)
                should_update |= set_optimistic(ATTR_EFFECT, kwargs[ATTR_EFFECT])

        if ATTR_WHITE in kwargs and self._topic[CONF_WHITE_COMMAND_TOPIC] is not None:
            percent_white = float(kwargs[ATTR_WHITE]) / 255
            white_scale = self._config[CONF_WHITE_SCALE]
            device_white_value = min(round(percent_white * white_scale), white_scale)
            await publish(CONF_WHITE_COMMAND_TOPIC, device_white_value)
            should_update |= set_optimistic(
                ATTR_BRIGHTNESS,
                kwargs[ATTR_WHITE],
                ColorMode.WHITE,
            )

        if (
            ATTR_WHITE_VALUE in kwargs
            and self._topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None
        ):
            percent_white = float(kwargs[ATTR_WHITE_VALUE]) / 255
            white_scale = self._config[CONF_WHITE_VALUE_SCALE]
            device_white_value = min(round(percent_white * white_scale), white_scale)
            await publish(CONF_WHITE_VALUE_COMMAND_TOPIC, device_white_value)
            should_update |= set_optimistic(ATTR_WHITE_VALUE, kwargs[ATTR_WHITE_VALUE])

        if on_command_type == "last":
            await publish(CONF_COMMAND_TOPIC, self._payload["on"])
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
        await self.async_publish(
            self._topic[CONF_COMMAND_TOPIC],
            self._payload["off"],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = False
            self.async_write_ha_state()
