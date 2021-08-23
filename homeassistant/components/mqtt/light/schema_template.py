"""Support for MQTT Template lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_STATE_TEMPLATE,
    STATE_OFF,
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
from .schema_basic import MQTT_LIGHT_ATTRIBUTES_BLOCKED

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt_template"

DEFAULT_NAME = "MQTT Template Light"
DEFAULT_OPTIMISTIC = False

CONF_BLUE_TEMPLATE = "blue_template"
CONF_BRIGHTNESS_TEMPLATE = "brightness_template"
CONF_COLOR_TEMP_TEMPLATE = "color_temp_template"
CONF_COMMAND_OFF_TEMPLATE = "command_off_template"
CONF_COMMAND_ON_TEMPLATE = "command_on_template"
CONF_EFFECT_LIST = "effect_list"
CONF_EFFECT_TEMPLATE = "effect_template"
CONF_GREEN_TEMPLATE = "green_template"
CONF_MAX_MIREDS = "max_mireds"
CONF_MIN_MIREDS = "min_mireds"
CONF_RED_TEMPLATE = "red_template"
CONF_WHITE_VALUE_TEMPLATE = "white_value_template"

PLATFORM_SCHEMA_TEMPLATE = (
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_BLUE_TEMPLATE): cv.template,
            vol.Optional(CONF_BRIGHTNESS_TEMPLATE): cv.template,
            vol.Optional(CONF_COLOR_TEMP_TEMPLATE): cv.template,
            vol.Required(CONF_COMMAND_OFF_TEMPLATE): cv.template,
            vol.Required(CONF_COMMAND_ON_TEMPLATE): cv.template,
            vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_EFFECT_TEMPLATE): cv.template,
            vol.Optional(CONF_GREEN_TEMPLATE): cv.template,
            vol.Optional(CONF_MAX_MIREDS): cv.positive_int,
            vol.Optional(CONF_MIN_MIREDS): cv.positive_int,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_RED_TEMPLATE): cv.template,
            vol.Optional(CONF_STATE_TEMPLATE): cv.template,
            vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
        }
    )
    .extend(MQTT_ENTITY_COMMON_SCHEMA.schema)
    .extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema)
)


async def async_setup_entity_template(
    hass, config, async_add_entities, config_entry, discovery_data
):
    """Set up a MQTT Template light."""
    async_add_entities([MqttLightTemplate(hass, config, config_entry, discovery_data)])


class MqttLightTemplate(MqttEntity, LightEntity, RestoreEntity):
    """Representation of a MQTT Template light."""

    _attributes_extra_blocked = MQTT_LIGHT_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize a MQTT Template light."""
        self._state = False

        self._topics = None
        self._templates = None
        self._optimistic = False

        # features
        self._brightness = None
        self._color_temp = None
        self._white_value = None
        self._hs = None
        self._effect = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA_TEMPLATE

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._topics = {
            key: config.get(key) for key in (CONF_STATE_TOPIC, CONF_COMMAND_TOPIC)
        }
        self._templates = {
            key: config.get(key)
            for key in (
                CONF_BLUE_TEMPLATE,
                CONF_BRIGHTNESS_TEMPLATE,
                CONF_COLOR_TEMP_TEMPLATE,
                CONF_COMMAND_OFF_TEMPLATE,
                CONF_COMMAND_ON_TEMPLATE,
                CONF_EFFECT_TEMPLATE,
                CONF_GREEN_TEMPLATE,
                CONF_RED_TEMPLATE,
                CONF_STATE_TEMPLATE,
                CONF_WHITE_VALUE_TEMPLATE,
            )
        }
        optimistic = config[CONF_OPTIMISTIC]
        self._optimistic = (
            optimistic
            or self._topics[CONF_STATE_TOPIC] is None
            or self._templates[CONF_STATE_TEMPLATE] is None
        )

    async def _subscribe_topics(self):  # noqa: C901
        """(Re)Subscribe to topics."""
        for tpl in self._templates.values():
            if tpl is not None:
                tpl.hass = self.hass

        last_state = await self.async_get_last_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_received(msg):
            """Handle new MQTT messages."""
            state = self._templates[
                CONF_STATE_TEMPLATE
            ].async_render_with_possible_json_value(msg.payload)
            if state == STATE_ON:
                self._state = True
            elif state == STATE_OFF:
                self._state = False
            else:
                _LOGGER.warning("Invalid state value received")

            if self._templates[CONF_BRIGHTNESS_TEMPLATE] is not None:
                try:
                    self._brightness = int(
                        self._templates[
                            CONF_BRIGHTNESS_TEMPLATE
                        ].async_render_with_possible_json_value(msg.payload)
                    )
                except ValueError:
                    _LOGGER.warning("Invalid brightness value received")

            if self._templates[CONF_COLOR_TEMP_TEMPLATE] is not None:
                try:
                    self._color_temp = int(
                        self._templates[
                            CONF_COLOR_TEMP_TEMPLATE
                        ].async_render_with_possible_json_value(msg.payload)
                    )
                except ValueError:
                    _LOGGER.warning("Invalid color temperature value received")

            if (
                self._templates[CONF_RED_TEMPLATE] is not None
                and self._templates[CONF_GREEN_TEMPLATE] is not None
                and self._templates[CONF_BLUE_TEMPLATE] is not None
            ):
                try:
                    red = int(
                        self._templates[
                            CONF_RED_TEMPLATE
                        ].async_render_with_possible_json_value(msg.payload)
                    )
                    green = int(
                        self._templates[
                            CONF_GREEN_TEMPLATE
                        ].async_render_with_possible_json_value(msg.payload)
                    )
                    blue = int(
                        self._templates[
                            CONF_BLUE_TEMPLATE
                        ].async_render_with_possible_json_value(msg.payload)
                    )
                    self._hs = color_util.color_RGB_to_hs(red, green, blue)
                except ValueError:
                    _LOGGER.warning("Invalid color value received")

            if self._templates[CONF_WHITE_VALUE_TEMPLATE] is not None:
                try:
                    self._white_value = int(
                        self._templates[
                            CONF_WHITE_VALUE_TEMPLATE
                        ].async_render_with_possible_json_value(msg.payload)
                    )
                except ValueError:
                    _LOGGER.warning("Invalid white value received")

            if self._templates[CONF_EFFECT_TEMPLATE] is not None:
                effect = self._templates[
                    CONF_EFFECT_TEMPLATE
                ].async_render_with_possible_json_value(msg.payload)

                if effect in self._config.get(CONF_EFFECT_LIST):
                    self._effect = effect
                else:
                    _LOGGER.warning("Unsupported effect value received")

            self.async_write_ha_state()

        if self._topics[CONF_STATE_TOPIC] is not None:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._topics[CONF_STATE_TOPIC],
                        "msg_callback": state_received,
                        "qos": self._config[CONF_QOS],
                    }
                },
            )

        if self._optimistic and last_state:
            self._state = last_state.state == STATE_ON
            if last_state.attributes.get(ATTR_BRIGHTNESS):
                self._brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            if last_state.attributes.get(ATTR_HS_COLOR):
                self._hs = last_state.attributes.get(ATTR_HS_COLOR)
            if last_state.attributes.get(ATTR_COLOR_TEMP):
                self._color_temp = last_state.attributes.get(ATTR_COLOR_TEMP)
            if last_state.attributes.get(ATTR_EFFECT):
                self._effect = last_state.attributes.get(ATTR_EFFECT)
            if last_state.attributes.get(ATTR_WHITE_VALUE):
                self._white_value = last_state.attributes.get(ATTR_WHITE_VALUE)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._config.get(CONF_MIN_MIREDS, super().min_mireds)

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._config.get(CONF_MAX_MIREDS, super().max_mireds)

    @property
    def hs_color(self):
        """Return the hs color value [int, int]."""
        return self._hs

    @property
    def white_value(self):
        """Return the white property."""
        return self._white_value

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return self._optimistic

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._config.get(CONF_EFFECT_LIST)

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    async def async_turn_on(self, **kwargs):
        """Turn the entity on.

        This method is a coroutine.
        """
        values = {"state": True}
        if self._optimistic:
            self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            values["brightness"] = int(kwargs[ATTR_BRIGHTNESS])

            if self._optimistic:
                self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP in kwargs:
            values["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._color_temp = kwargs[ATTR_COLOR_TEMP]

        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]

            # If there's a brightness topic set, we don't want to scale the RGB
            # values given using the brightness.
            if self._templates[CONF_BRIGHTNESS_TEMPLATE] is not None:
                brightness = 255
            else:
                brightness = kwargs.get(
                    ATTR_BRIGHTNESS,
                    self._brightness if self._brightness is not None else 255,
                )
            rgb = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], brightness / 255 * 100
            )
            values["red"] = rgb[0]
            values["green"] = rgb[1]
            values["blue"] = rgb[2]

            if self._optimistic:
                self._hs = kwargs[ATTR_HS_COLOR]

        if ATTR_WHITE_VALUE in kwargs:
            values["white_value"] = int(kwargs[ATTR_WHITE_VALUE])

            if self._optimistic:
                self._white_value = kwargs[ATTR_WHITE_VALUE]

        if ATTR_EFFECT in kwargs:
            values["effect"] = kwargs.get(ATTR_EFFECT)

            if self._optimistic:
                self._effect = kwargs[ATTR_EFFECT]

        if ATTR_FLASH in kwargs:
            values["flash"] = kwargs.get(ATTR_FLASH)

        if ATTR_TRANSITION in kwargs:
            values["transition"] = kwargs[ATTR_TRANSITION]

        mqtt.async_publish(
            self.hass,
            self._topics[CONF_COMMAND_TOPIC],
            self._templates[CONF_COMMAND_ON_TEMPLATE].async_render(
                parse_result=False, **values
            ),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off.

        This method is a coroutine.
        """
        values = {"state": False}
        if self._optimistic:
            self._state = False

        if ATTR_TRANSITION in kwargs:
            values["transition"] = kwargs[ATTR_TRANSITION]

        mqtt.async_publish(
            self.hass,
            self._topics[CONF_COMMAND_TOPIC],
            self._templates[CONF_COMMAND_OFF_TEMPLATE].async_render(
                parse_result=False, **values
            ),
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

        if self._optimistic:
            self.async_write_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        features = SUPPORT_FLASH | SUPPORT_TRANSITION
        if self._templates[CONF_BRIGHTNESS_TEMPLATE] is not None:
            features = features | SUPPORT_BRIGHTNESS
        if (
            self._templates[CONF_RED_TEMPLATE] is not None
            and self._templates[CONF_GREEN_TEMPLATE] is not None
            and self._templates[CONF_BLUE_TEMPLATE] is not None
        ):
            features = features | SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        if self._config.get(CONF_EFFECT_LIST) is not None:
            features = features | SUPPORT_EFFECT
        if self._templates[CONF_COLOR_TEMP_TEMPLATE] is not None:
            features = features | SUPPORT_COLOR_TEMP
        if self._templates[CONF_WHITE_VALUE_TEMPLATE] is not None:
            features = features | SUPPORT_WHITE_VALUE

        return features
