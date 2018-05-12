"""
Support for MQTT Template lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt_template/
"""
import logging
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH,
    ATTR_HS_COLOR, ATTR_TRANSITION, ATTR_WHITE_VALUE, Light, PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_COLOR, SUPPORT_TRANSITION, SUPPORT_WHITE_VALUE)
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, STATE_ON, STATE_OFF
from homeassistant.components.mqtt import (
    CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC, CONF_COMMAND_TOPIC,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS, CONF_RETAIN,
    MqttAvailability)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util
from homeassistant.helpers.restore_state import async_get_last_state

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mqtt_template'

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT Template Light'
DEFAULT_OPTIMISTIC = False

CONF_BLUE_TEMPLATE = 'blue_template'
CONF_BRIGHTNESS_TEMPLATE = 'brightness_template'
CONF_COLOR_TEMP_TEMPLATE = 'color_temp_template'
CONF_COMMAND_OFF_TEMPLATE = 'command_off_template'
CONF_COMMAND_ON_TEMPLATE = 'command_on_template'
CONF_EFFECT_LIST = 'effect_list'
CONF_EFFECT_TEMPLATE = 'effect_template'
CONF_GREEN_TEMPLATE = 'green_template'
CONF_RED_TEMPLATE = 'red_template'
CONF_STATE_TEMPLATE = 'state_template'
CONF_WHITE_VALUE_TEMPLATE = 'white_value_template'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BLUE_TEMPLATE): cv.template,
    vol.Optional(CONF_BRIGHTNESS_TEMPLATE): cv.template,
    vol.Optional(CONF_COLOR_TEMP_TEMPLATE): cv.template,
    vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_EFFECT_TEMPLATE): cv.template,
    vol.Optional(CONF_GREEN_TEMPLATE): cv.template,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_RED_TEMPLATE): cv.template,
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    vol.Optional(CONF_STATE_TEMPLATE): cv.template,
    vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
    vol.Required(CONF_COMMAND_OFF_TEMPLATE): cv.template,
    vol.Required(CONF_COMMAND_ON_TEMPLATE): cv.template,
    vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_QOS, default=mqtt.DEFAULT_QOS):
        vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up a MQTT Template light."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)

    async_add_devices([MqttTemplate(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_EFFECT_LIST),
        {
            key: config.get(key) for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC
            )
        },
        {
            key: config.get(key) for key in (
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
        },
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
    )])


class MqttTemplate(MqttAvailability, Light):
    """Representation of a MQTT Template light."""

    def __init__(self, hass, name, effect_list, topics, templates, optimistic,
                 qos, retain, availability_topic, payload_available,
                 payload_not_available):
        """Initialize a MQTT Template light."""
        super().__init__(availability_topic, qos, payload_available,
                         payload_not_available)
        self._name = name
        self._effect_list = effect_list
        self._topics = topics
        self._templates = templates
        self._optimistic = optimistic or topics[CONF_STATE_TOPIC] is None \
            or templates[CONF_STATE_TEMPLATE] is None
        self._qos = qos
        self._retain = retain

        # features
        self._state = False
        if self._templates[CONF_BRIGHTNESS_TEMPLATE] is not None:
            self._brightness = 255
        else:
            self._brightness = None

        if self._templates[CONF_COLOR_TEMP_TEMPLATE] is not None:
            self._color_temp = 255
        else:
            self._color_temp = None

        if self._templates[CONF_WHITE_VALUE_TEMPLATE] is not None:
            self._white_value = 255
        else:
            self._white_value = None

        if (self._templates[CONF_RED_TEMPLATE] is not None and
                self._templates[CONF_GREEN_TEMPLATE] is not None and
                self._templates[CONF_BLUE_TEMPLATE] is not None):
            self._hs = [0, 0]
        else:
            self._hs = None
        self._effect = None

        for tpl in self._templates.values():
            if tpl is not None:
                tpl.hass = hass

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

        last_state = await async_get_last_state(self.hass, self.entity_id)

        @callback
        def state_received(topic, payload, qos):
            """Handle new MQTT messages."""
            state = self._templates[CONF_STATE_TEMPLATE].\
                async_render_with_possible_json_value(payload)
            if state == STATE_ON:
                self._state = True
            elif state == STATE_OFF:
                self._state = False
            else:
                _LOGGER.warning("Invalid state value received")

            if self._brightness is not None:
                try:
                    self._brightness = int(
                        self._templates[CONF_BRIGHTNESS_TEMPLATE].
                        async_render_with_possible_json_value(payload)
                    )
                except ValueError:
                    _LOGGER.warning("Invalid brightness value received")

            if self._color_temp is not None:
                try:
                    self._color_temp = int(
                        self._templates[CONF_COLOR_TEMP_TEMPLATE].
                        async_render_with_possible_json_value(payload)
                    )
                except ValueError:
                    _LOGGER.warning("Invalid color temperature value received")

            if self._hs is not None:
                try:
                    red = int(
                        self._templates[CONF_RED_TEMPLATE].
                        async_render_with_possible_json_value(payload))
                    green = int(
                        self._templates[CONF_GREEN_TEMPLATE].
                        async_render_with_possible_json_value(payload))
                    blue = int(
                        self._templates[CONF_BLUE_TEMPLATE].
                        async_render_with_possible_json_value(payload))
                    self._hs = color_util.color_RGB_to_hs(red, green, blue)
                except ValueError:
                    _LOGGER.warning("Invalid color value received")

            if self._white_value is not None:
                try:
                    self._white_value = int(
                        self._templates[CONF_WHITE_VALUE_TEMPLATE].
                        async_render_with_possible_json_value(payload)
                    )
                except ValueError:
                    _LOGGER.warning('Invalid white value received')

            if self._templates[CONF_EFFECT_TEMPLATE] is not None:
                effect = self._templates[CONF_EFFECT_TEMPLATE].\
                    async_render_with_possible_json_value(payload)

                if effect in self._effect_list:
                    self._effect = effect
                else:
                    _LOGGER.warning("Unsupported effect value received")

            self.async_schedule_update_ha_state()

        if self._topics[CONF_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topics[CONF_STATE_TOPIC], state_received,
                self._qos)

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
    def hs_color(self):
        """Return the hs color value [int, int]."""
        return self._hs

    @property
    def white_value(self):
        """Return the white property."""
        return self._white_value

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

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
        return self._effect_list

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    async def async_turn_on(self, **kwargs):
        """Turn the entity on.

        This method is a coroutine.
        """
        values = {'state': True}
        if self._optimistic:
            self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            values['brightness'] = int(kwargs[ATTR_BRIGHTNESS])

            if self._optimistic:
                self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP in kwargs:
            values['color_temp'] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._color_temp = kwargs[ATTR_COLOR_TEMP]

        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            brightness = kwargs.get(
                ATTR_BRIGHTNESS, self._brightness if self._brightness else 255)
            rgb = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], brightness / 255 * 100)
            values['red'] = rgb[0]
            values['green'] = rgb[1]
            values['blue'] = rgb[2]

            if self._optimistic:
                self._hs = kwargs[ATTR_HS_COLOR]

        if ATTR_WHITE_VALUE in kwargs:
            values['white_value'] = int(kwargs[ATTR_WHITE_VALUE])

            if self._optimistic:
                self._white_value = kwargs[ATTR_WHITE_VALUE]

        if ATTR_EFFECT in kwargs:
            values['effect'] = kwargs.get(ATTR_EFFECT)

        if ATTR_FLASH in kwargs:
            values['flash'] = kwargs.get(ATTR_FLASH)

        if ATTR_TRANSITION in kwargs:
            values['transition'] = int(kwargs[ATTR_TRANSITION])

        mqtt.async_publish(
            self.hass, self._topics[CONF_COMMAND_TOPIC],
            self._templates[CONF_COMMAND_ON_TEMPLATE].async_render(**values),
            self._qos, self._retain
        )

        if self._optimistic:
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off.

        This method is a coroutine.
        """
        values = {'state': False}
        if self._optimistic:
            self._state = False

        if ATTR_TRANSITION in kwargs:
            values['transition'] = int(kwargs[ATTR_TRANSITION])

        mqtt.async_publish(
            self.hass, self._topics[CONF_COMMAND_TOPIC],
            self._templates[CONF_COMMAND_OFF_TEMPLATE].async_render(**values),
            self._qos, self._retain
        )

        if self._optimistic:
            self.async_schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        features = (SUPPORT_FLASH | SUPPORT_TRANSITION)
        if self._brightness is not None:
            features = features | SUPPORT_BRIGHTNESS
        if self._hs is not None:
            features = features | SUPPORT_COLOR
        if self._effect_list is not None:
            features = features | SUPPORT_EFFECT
        if self._color_temp is not None:
            features = features | SUPPORT_COLOR_TEMP
        if self._white_value is not None:
            features = features | SUPPORT_WHITE_VALUE

        return features
