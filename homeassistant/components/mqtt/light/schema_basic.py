"""Support for MQTT lights."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, cast

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
    ATTR_XY_COLOR,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    valid_supported_color_modes,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
from ..models import (
    MessageCallbackType,
    MqttCommandTemplate,
    MqttValueTemplate,
    PayloadSentinel,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
    TemplateVarsType,
)
from ..util import get_mqtt_data, valid_publish_topic, valid_subscribe_topic
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
CONF_HS_COMMAND_TEMPLATE = "hs_command_template"
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
CONF_XY_COMMAND_TEMPLATE = "xy_command_template"
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
        ATTR_XY_COLOR,
    }
)

DEFAULT_BRIGHTNESS_SCALE = 255
DEFAULT_NAME = "MQTT LightEntity"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_WHITE_SCALE = 255
DEFAULT_ON_COMMAND_TYPE = "last"

VALUES_ON_COMMAND_TYPE = ["first", "last", "brightness"]

COMMAND_TEMPLATE_KEYS = [
    CONF_BRIGHTNESS_COMMAND_TEMPLATE,
    CONF_COLOR_TEMP_COMMAND_TEMPLATE,
    CONF_EFFECT_COMMAND_TEMPLATE,
    CONF_HS_COMMAND_TEMPLATE,
    CONF_RGB_COMMAND_TEMPLATE,
    CONF_RGBW_COMMAND_TEMPLATE,
    CONF_RGBWW_COMMAND_TEMPLATE,
    CONF_XY_COMMAND_TEMPLATE,
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
            vol.Optional(CONF_HS_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_HS_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_HS_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_HS_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_ON_COMMAND_TYPE, default=DEFAULT_ON_COMMAND_TYPE): vol.In(
                VALUES_ON_COMMAND_TYPE
            ),
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
            vol.Optional(CONF_XY_COMMAND_TEMPLATE): cv.template,
            vol.Optional(CONF_XY_COMMAND_TOPIC): valid_publish_topic,
            vol.Optional(CONF_XY_STATE_TOPIC): valid_subscribe_topic,
            vol.Optional(CONF_XY_VALUE_TEMPLATE): cv.template,
        },
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)

DISCOVERY_SCHEMA_BASIC = vol.All(
    # CONF_WHITE_VALUE_* is no longer supported, support was removed in 2022.9
    cv.removed(CONF_WHITE_VALUE_COMMAND_TOPIC),
    cv.removed(CONF_WHITE_VALUE_SCALE),
    cv.removed(CONF_WHITE_VALUE_STATE_TOPIC),
    cv.removed(CONF_WHITE_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
)

PLATFORM_SCHEMA_MODERN_BASIC = vol.All(
    # CONF_WHITE_VALUE_* is no longer supported, support was removed in 2022.9
    cv.removed(CONF_WHITE_VALUE_COMMAND_TOPIC),
    cv.removed(CONF_WHITE_VALUE_SCALE),
    cv.removed(CONF_WHITE_VALUE_STATE_TOPIC),
    cv.removed(CONF_WHITE_VALUE_TEMPLATE),
    _PLATFORM_SCHEMA_BASE,
)


async def async_setup_entity_basic(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None,
) -> None:
    """Set up a MQTT Light."""
    async_add_entities([MqttLight(hass, config, config_entry, discovery_data)])


class MqttLight(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT light."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED
    _topic: dict[str, str | None]
    _payload: dict[str, str]
    _command_templates: dict[
        str, Callable[[PublishPayloadType, TemplateVarsType], PublishPayloadType]
    ]
    _value_templates: dict[
        str, Callable[[ReceivePayloadType, ReceivePayloadType], ReceivePayloadType]
    ]
    _optimistic: bool
    _optimistic_brightness: bool
    _optimistic_color_mode: bool
    _optimistic_color_temp: bool
    _optimistic_effect: bool
    _optimistic_hs_color: bool
    _optimistic_rgb_color: bool
    _optimistic_rgbw_color: bool
    _optimistic_rgbww_color: bool
    _optimistic_xy_color: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize MQTT light."""
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA_BASIC

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_min_mireds = config.get(CONF_MIN_MIREDS, super().min_mireds)
        self._attr_max_mireds = config.get(CONF_MAX_MIREDS, super().max_mireds)
        self._attr_effect_list = config.get(CONF_EFFECT_LIST)

        topic: dict[str, str | None] = {
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
                CONF_XY_COMMAND_TOPIC,
                CONF_XY_STATE_TOPIC,
            )
        }
        self._topic = topic
        self._payload = {"on": config[CONF_PAYLOAD_ON], "off": config[CONF_PAYLOAD_OFF]}

        self._value_templates = {
            key: MqttValueTemplate(
                config.get(key), entity=self
            ).async_render_with_possible_json_value
            for key in VALUE_TEMPLATE_KEYS
        }

        self._command_templates = {
            key: MqttCommandTemplate(config.get(key), entity=self).async_render
            for key in COMMAND_TEMPLATE_KEYS
        }

        optimistic: bool = config[CONF_OPTIMISTIC]
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
        self._optimistic_xy_color = optimistic or topic[CONF_XY_STATE_TOPIC] is None
        supported_color_modes: set[ColorMode] = set()
        if topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        if topic[CONF_HS_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.HS)
            self._attr_color_mode = ColorMode.HS
        if topic[CONF_RGB_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.RGB)
            self._attr_color_mode = ColorMode.RGB
        if topic[CONF_RGBW_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.RGBW)
            self._attr_color_mode = ColorMode.RGBW
        if topic[CONF_RGBWW_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.RGBWW)
            self._attr_color_mode = ColorMode.RGBWW
        if topic[CONF_WHITE_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.WHITE)
        if topic[CONF_XY_COMMAND_TOPIC] is not None:
            supported_color_modes.add(ColorMode.XY)
            self._attr_color_mode = ColorMode.XY
        if len(supported_color_modes) > 1:
            self._attr_color_mode = ColorMode.UNKNOWN

        if not supported_color_modes:
            if topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
                self._attr_color_mode = ColorMode.BRIGHTNESS
                supported_color_modes.add(ColorMode.BRIGHTNESS)
            else:
                self._attr_color_mode = ColorMode.ONOFF
                supported_color_modes.add(ColorMode.ONOFF)

        # Validate the color_modes configuration
        self._attr_supported_color_modes = valid_supported_color_modes(
            supported_color_modes
        )

        self._attr_supported_features = LightEntityFeature(0)
        if topic[CONF_EFFECT_COMMAND_TOPIC] is not None:
            self._attr_supported_features |= LightEntityFeature.EFFECT

    def _is_optimistic(self, attribute: str) -> bool:
        """Return True if the attribute is optimistically updated."""
        attr: bool = getattr(self, f"_optimistic_{attribute}")
        return attr

    def _prepare_subscribe_topics(self) -> None:  # noqa: C901
        """(Re)Subscribe to topics."""
        topics: dict[str, dict[str, Any]] = {}

        def add_topic(topic: str, msg_callback: MessageCallbackType) -> None:
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
        def state_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages."""
            payload = self._value_templates[CONF_STATE_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.NONE
            )
            if not payload:
                _LOGGER.debug("Ignoring empty state message from '%s'", msg.topic)
                return

            if payload == self._payload["on"]:
                self._attr_is_on = True
            elif payload == self._payload["off"]:
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
        def brightness_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for the brightness."""
            payload = self._value_templates[CONF_BRIGHTNESS_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug("Ignoring empty brightness message from '%s'", msg.topic)
                return

            device_value = float(payload)
            if device_value == 0:
                _LOGGER.debug("Ignoring zero brightness from '%s'", msg.topic)
                return

            percent_bright = device_value / self._config[CONF_BRIGHTNESS_SCALE]
            self._attr_brightness = min(round(percent_bright * 255), 255)

            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_BRIGHTNESS_STATE_TOPIC, brightness_received)

        def _rgbx_received(
            msg: ReceiveMessage,
            template: str,
            color_mode: ColorMode,
            convert_color: Callable[..., tuple[int, ...]],
        ) -> tuple[int, ...] | None:
            """Handle new MQTT messages for RGBW and RGBWW."""
            payload = self._value_templates[template](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug(
                    "Ignoring empty %s message from '%s'", color_mode, msg.topic
                )
                return None
            color = tuple(int(val) for val in str(payload).split(","))
            if self._optimistic_color_mode:
                self._attr_color_mode = color_mode
            if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is None:
                rgb = convert_color(*color)
                brightness = max(rgb)
                self._attr_brightness = brightness
                # Normalize the color to 100% brightness
                color = tuple(
                    min(round(channel / brightness * 255), 255) for channel in color
                )
            return color

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgb_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for RGB."""
            rgb = _rgbx_received(
                msg, CONF_RGB_VALUE_TEMPLATE, ColorMode.RGB, lambda *x: x
            )
            if rgb is None:
                return
            self._attr_rgb_color = cast(tuple[int, int, int], rgb)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_RGB_STATE_TOPIC, rgb_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgbw_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for RGBW."""
            rgbw = _rgbx_received(
                msg,
                CONF_RGBW_VALUE_TEMPLATE,
                ColorMode.RGBW,
                color_util.color_rgbw_to_rgb,
            )
            if rgbw is None:
                return
            self._attr_rgbw_color = cast(tuple[int, int, int, int], rgbw)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_RGBW_STATE_TOPIC, rgbw_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def rgbww_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for RGBWW."""
            rgbww = _rgbx_received(
                msg,
                CONF_RGBWW_VALUE_TEMPLATE,
                ColorMode.RGBWW,
                color_util.color_rgbww_to_rgb,
            )
            if rgbww is None:
                return
            self._attr_rgbww_color = cast(tuple[int, int, int, int, int], rgbww)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_RGBWW_STATE_TOPIC, rgbww_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def color_mode_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for color mode."""
            payload = self._value_templates[CONF_COLOR_MODE_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug("Ignoring empty color mode message from '%s'", msg.topic)
                return

            self._attr_color_mode = str(payload)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_COLOR_MODE_STATE_TOPIC, color_mode_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def color_temp_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for color temperature."""
            payload = self._value_templates[CONF_COLOR_TEMP_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug("Ignoring empty color temp message from '%s'", msg.topic)
                return

            if self._optimistic_color_mode:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp = int(payload)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_COLOR_TEMP_STATE_TOPIC, color_temp_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def effect_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for effect."""
            payload = self._value_templates[CONF_EFFECT_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug("Ignoring empty effect message from '%s'", msg.topic)
                return

            self._attr_effect = str(payload)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_EFFECT_STATE_TOPIC, effect_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def hs_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for hs color."""
            payload = self._value_templates[CONF_HS_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug("Ignoring empty hs message from '%s'", msg.topic)
                return
            try:
                hs_color = tuple(float(val) for val in str(payload).split(",", 2))
                if self._optimistic_color_mode:
                    self._attr_color_mode = ColorMode.HS
                self._attr_hs_color = cast(tuple[float, float], hs_color)
                get_mqtt_data(self.hass).state_write_requests.write_state_request(self)
            except ValueError:
                _LOGGER.warning("Failed to parse hs state update: '%s'", payload)

        add_topic(CONF_HS_STATE_TOPIC, hs_received)

        @callback
        @log_messages(self.hass, self.entity_id)
        def xy_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT messages for xy color."""
            payload = self._value_templates[CONF_XY_VALUE_TEMPLATE](
                msg.payload, PayloadSentinel.DEFAULT
            )
            if payload is PayloadSentinel.DEFAULT or not payload:
                _LOGGER.debug("Ignoring empty xy-color message from '%s'", msg.topic)
                return

            xy_color = tuple(float(val) for val in str(payload).split(",", 2))
            if self._optimistic_color_mode:
                self._attr_color_mode = ColorMode.XY
            self._attr_xy_color = cast(tuple[float, float], xy_color)
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        add_topic(CONF_XY_STATE_TOPIC, xy_received)

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass, self._sub_state, topics
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)
        last_state = await self.async_get_last_state()

        def restore_state(
            attribute: str, condition_attribute: str | None = None
        ) -> None:
            """Restore a state attribute."""
            if condition_attribute is None:
                condition_attribute = attribute
            optimistic = self._is_optimistic(condition_attribute)
            if optimistic and last_state and last_state.attributes.get(attribute):
                setattr(self, f"_attr_{attribute}", last_state.attributes[attribute])

        if self._topic[CONF_STATE_TOPIC] is None and self._optimistic and last_state:
            self._attr_is_on = last_state.state == STATE_ON
        restore_state(ATTR_BRIGHTNESS)
        restore_state(ATTR_RGB_COLOR)
        restore_state(ATTR_HS_COLOR, ATTR_RGB_COLOR)
        restore_state(ATTR_RGBW_COLOR)
        restore_state(ATTR_RGBWW_COLOR)
        restore_state(ATTR_COLOR_MODE)
        restore_state(ATTR_COLOR_TEMP)
        restore_state(ATTR_EFFECT)
        restore_state(ATTR_HS_COLOR)
        restore_state(ATTR_XY_COLOR)
        restore_state(ATTR_HS_COLOR, ATTR_XY_COLOR)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: C901
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False
        on_command_type: str = self._config[CONF_ON_COMMAND_TYPE]

        async def publish(topic: str, payload: PublishPayloadType) -> None:
            """Publish an MQTT message."""
            await self.async_publish(
                str(self._topic[topic]),
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

        def scale_rgbx(
            color: tuple[int, ...],
            brightness: int | None = None,
        ) -> tuple[int, ...]:
            """Scale RGBx for brightness."""
            if brightness is None:
                # If there's a brightness topic set, we don't want to scale the RGBx
                # values given using the brightness.
                if self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
                    brightness = 255
                else:
                    brightness = kwargs.get(ATTR_BRIGHTNESS) or self.brightness or 255
            return tuple(int(channel * brightness / 255) for channel in color)

        def render_rgbx(
            color: tuple[int, ...],
            template: str,
            color_mode: ColorMode,
        ) -> PublishPayloadType:
            """Render RGBx payload."""
            rgb_color_str = ",".join(str(channel) for channel in color)
            keys = ["red", "green", "blue"]
            if color_mode == ColorMode.RGBW:
                keys.append("white")
            elif color_mode == ColorMode.RGBWW:
                keys.extend(["cold_white", "warm_white"])
            variables = dict(zip(keys, color))
            return self._command_templates[template](rgb_color_str, variables)

        def set_optimistic(
            attribute: str,
            value: Any,
            color_mode: ColorMode | None = None,
            condition_attribute: str | None = None,
        ) -> bool:
            """Optimistically update a state attribute."""
            if condition_attribute is None:
                condition_attribute = attribute
            if not self._is_optimistic(condition_attribute):
                return False
            if color_mode and self._optimistic_color_mode:
                self._attr_color_mode = color_mode

            setattr(self, f"_attr_{attribute}", value)
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
            kwargs[ATTR_BRIGHTNESS] = self.brightness or 255

        hs_color: str | None = kwargs.get(ATTR_HS_COLOR)

        if hs_color and self._topic[CONF_HS_COMMAND_TOPIC] is not None:
            device_hs_payload = self._command_templates[CONF_HS_COMMAND_TEMPLATE](
                f"{hs_color[0]},{hs_color[1]}",
                {"hue": hs_color[0], "sat": hs_color[1]},
            )
            await publish(CONF_HS_COMMAND_TOPIC, device_hs_payload)
            should_update |= set_optimistic(ATTR_HS_COLOR, hs_color, ColorMode.HS)

        rgb: tuple[int, int, int] | None
        if (rgb := kwargs.get(ATTR_RGB_COLOR)) and self._topic[
            CONF_RGB_COMMAND_TOPIC
        ] is not None:
            scaled = scale_rgbx(rgb)
            rgb_s = render_rgbx(scaled, CONF_RGB_COMMAND_TEMPLATE, ColorMode.RGB)
            await publish(CONF_RGB_COMMAND_TOPIC, rgb_s)
            should_update |= set_optimistic(ATTR_RGB_COLOR, rgb, ColorMode.RGB)

        rgbw: tuple[int, int, int, int] | None
        if (rgbw := kwargs.get(ATTR_RGBW_COLOR)) and self._topic[
            CONF_RGBW_COMMAND_TOPIC
        ] is not None:
            scaled = scale_rgbx(rgbw)
            rgbw_s = render_rgbx(scaled, CONF_RGBW_COMMAND_TEMPLATE, ColorMode.RGBW)
            await publish(CONF_RGBW_COMMAND_TOPIC, rgbw_s)
            should_update |= set_optimistic(ATTR_RGBW_COLOR, rgbw, ColorMode.RGBW)

        rgbww: tuple[int, int, int, int, int] | None
        if (rgbww := kwargs.get(ATTR_RGBWW_COLOR)) and self._topic[
            CONF_RGBWW_COMMAND_TOPIC
        ] is not None:
            scaled = scale_rgbx(rgbww)
            rgbww_s = render_rgbx(scaled, CONF_RGBWW_COMMAND_TEMPLATE, ColorMode.RGBWW)
            await publish(CONF_RGBWW_COMMAND_TOPIC, rgbww_s)
            should_update |= set_optimistic(ATTR_RGBWW_COLOR, rgbww, ColorMode.RGBWW)

        xy_color: tuple[float, float] | None
        if (xy_color := kwargs.get(ATTR_XY_COLOR)) and self._topic[
            CONF_XY_COMMAND_TOPIC
        ] is not None:
            device_xy_payload = self._command_templates[CONF_XY_COMMAND_TEMPLATE](
                f"{xy_color[0]},{xy_color[1]}",
                {"x": xy_color[0], "y": xy_color[1]},
            )
            await publish(CONF_XY_COMMAND_TOPIC, device_xy_payload)
            should_update |= set_optimistic(ATTR_XY_COLOR, xy_color, ColorMode.XY)

        if (
            ATTR_BRIGHTNESS in kwargs
            and self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None
        ):
            brightness_normalized: float = kwargs[ATTR_BRIGHTNESS] / 255
            brightness_scale: int = self._config[CONF_BRIGHTNESS_SCALE]
            device_brightness = min(
                round(brightness_normalized * brightness_scale), brightness_scale
            )
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)
            command_tpl = self._command_templates[CONF_BRIGHTNESS_COMMAND_TEMPLATE]
            device_brightness_payload = command_tpl(device_brightness, None)
            await publish(CONF_BRIGHTNESS_COMMAND_TOPIC, device_brightness_payload)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_RGB_COLOR not in kwargs
            and self._topic[CONF_RGB_COMMAND_TOPIC] is not None
        ):
            rgb_color = self.rgb_color or (255,) * 3
            rgb_scaled = scale_rgbx(rgb_color, kwargs[ATTR_BRIGHTNESS])
            rgb_s = render_rgbx(rgb_scaled, CONF_RGB_COMMAND_TEMPLATE, ColorMode.RGB)
            await publish(CONF_RGB_COMMAND_TOPIC, rgb_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_RGBW_COLOR not in kwargs
            and self._topic[CONF_RGBW_COMMAND_TOPIC] is not None
        ):
            rgbw_color = self.rgbw_color or (255,) * 4
            rgbw_b = scale_rgbx(rgbw_color, kwargs[ATTR_BRIGHTNESS])
            rgbw_s = render_rgbx(rgbw_b, CONF_RGBW_COMMAND_TEMPLATE, ColorMode.RGBW)
            await publish(CONF_RGBW_COMMAND_TOPIC, rgbw_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        elif (
            ATTR_BRIGHTNESS in kwargs
            and ATTR_RGBWW_COLOR not in kwargs
            and self._topic[CONF_RGBWW_COMMAND_TOPIC] is not None
        ):
            rgbww_color = self.rgbww_color or (255,) * 5
            rgbww_b = scale_rgbx(rgbww_color, kwargs[ATTR_BRIGHTNESS])
            rgbww_s = render_rgbx(rgbww_b, CONF_RGBWW_COMMAND_TEMPLATE, ColorMode.RGBWW)
            await publish(CONF_RGBWW_COMMAND_TOPIC, rgbww_s)
            should_update |= set_optimistic(ATTR_BRIGHTNESS, kwargs[ATTR_BRIGHTNESS])
        if (
            ATTR_COLOR_TEMP in kwargs
            and self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None
        ):
            ct_command_tpl = self._command_templates[CONF_COLOR_TEMP_COMMAND_TEMPLATE]
            color_temp = ct_command_tpl(int(kwargs[ATTR_COLOR_TEMP]), None)
            await publish(CONF_COLOR_TEMP_COMMAND_TOPIC, color_temp)
            should_update |= set_optimistic(
                ATTR_COLOR_TEMP, kwargs[ATTR_COLOR_TEMP], ColorMode.COLOR_TEMP
            )

        if (
            ATTR_EFFECT in kwargs
            and self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None
            and CONF_EFFECT_LIST in self._config
        ):
            if kwargs[ATTR_EFFECT] in self._config[CONF_EFFECT_LIST]:
                eff_command_tpl = self._command_templates[CONF_EFFECT_COMMAND_TEMPLATE]
                effect = eff_command_tpl(kwargs[ATTR_EFFECT], None)
                await publish(CONF_EFFECT_COMMAND_TOPIC, effect)
                should_update |= set_optimistic(ATTR_EFFECT, kwargs[ATTR_EFFECT])

        if ATTR_WHITE in kwargs and self._topic[CONF_WHITE_COMMAND_TOPIC] is not None:
            percent_white = float(kwargs[ATTR_WHITE]) / 255
            white_scale: int = self._config[CONF_WHITE_SCALE]
            device_white_value = min(round(percent_white * white_scale), white_scale)
            await publish(CONF_WHITE_COMMAND_TOPIC, device_white_value)
            should_update |= set_optimistic(
                ATTR_BRIGHTNESS,
                kwargs[ATTR_WHITE],
                ColorMode.WHITE,
            )

        if on_command_type == "last":
            await publish(CONF_COMMAND_TOPIC, self._payload["on"])
            should_update = True

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._attr_is_on = True
            should_update = True

        if should_update:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off.

        This method is a coroutine.
        """
        await self.async_publish(
            str(self._topic[CONF_COMMAND_TOPIC]),
            self._payload["off"],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._attr_is_on = False
            self.async_write_ha_state()
