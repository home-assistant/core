"""
Support for MQTT lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components import mqtt, light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_HS_COLOR,
    ATTR_WHITE_VALUE, Light, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT, SUPPORT_COLOR, SUPPORT_WHITE_VALUE)
from homeassistant.const import (
    CONF_BRIGHTNESS, CONF_COLOR_TEMP, CONF_EFFECT, CONF_HS, CONF_NAME,
    CONF_OPTIMISTIC, CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON, STATE_ON,
    CONF_RGB, CONF_STATE, CONF_VALUE_TEMPLATE, CONF_WHITE_VALUE, CONF_XY)
from homeassistant.components.mqtt import (
    ATTR_DISCOVERY_HASH, CONF_AVAILABILITY_TOPIC, CONF_COMMAND_TOPIC,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS, CONF_RETAIN,
    CONF_STATE_TOPIC, MqttAvailability, MqttDiscoveryUpdate)
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
from homeassistant.helpers.restore_state import async_get_last_state
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_BRIGHTNESS_COMMAND_TOPIC = 'brightness_command_topic'
CONF_BRIGHTNESS_SCALE = 'brightness_scale'
CONF_BRIGHTNESS_STATE_TOPIC = 'brightness_state_topic'
CONF_BRIGHTNESS_VALUE_TEMPLATE = 'brightness_value_template'
CONF_COLOR_TEMP_COMMAND_TOPIC = 'color_temp_command_topic'
CONF_COLOR_TEMP_STATE_TOPIC = 'color_temp_state_topic'
CONF_COLOR_TEMP_VALUE_TEMPLATE = 'color_temp_value_template'
CONF_EFFECT_COMMAND_TOPIC = 'effect_command_topic'
CONF_EFFECT_LIST = 'effect_list'
CONF_EFFECT_STATE_TOPIC = 'effect_state_topic'
CONF_EFFECT_VALUE_TEMPLATE = 'effect_value_template'
CONF_HS_COMMAND_TOPIC = 'hs_command_topic'
CONF_HS_STATE_TOPIC = 'hs_state_topic'
CONF_HS_VALUE_TEMPLATE = 'hs_value_template'
CONF_RGB_COMMAND_TEMPLATE = 'rgb_command_template'
CONF_RGB_COMMAND_TOPIC = 'rgb_command_topic'
CONF_RGB_STATE_TOPIC = 'rgb_state_topic'
CONF_RGB_VALUE_TEMPLATE = 'rgb_value_template'
CONF_STATE_VALUE_TEMPLATE = 'state_value_template'
CONF_XY_COMMAND_TOPIC = 'xy_command_topic'
CONF_XY_STATE_TOPIC = 'xy_state_topic'
CONF_XY_VALUE_TEMPLATE = 'xy_value_template'
CONF_WHITE_VALUE_COMMAND_TOPIC = 'white_value_command_topic'
CONF_WHITE_VALUE_SCALE = 'white_value_scale'
CONF_WHITE_VALUE_STATE_TOPIC = 'white_value_state_topic'
CONF_WHITE_VALUE_TEMPLATE = 'white_value_template'
CONF_ON_COMMAND_TYPE = 'on_command_type'
CONF_UNIQUE_ID = 'unique_id'

DEFAULT_BRIGHTNESS_SCALE = 255
DEFAULT_NAME = 'MQTT Light'
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_OFF = 'OFF'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_WHITE_VALUE_SCALE = 255
DEFAULT_ON_COMMAND_TYPE = 'last'

VALUES_ON_COMMAND_TYPE = ['first', 'last', 'brightness']

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BRIGHTNESS_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_BRIGHTNESS_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_BRIGHTNESS_VALUE_TEMPLATE): cv.template,
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
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_RGB_COMMAND_TEMPLATE): cv.template,
    vol.Optional(CONF_RGB_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_RGB_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_RGB_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_WHITE_VALUE_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_WHITE_VALUE_SCALE, default=DEFAULT_WHITE_VALUE_SCALE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_WHITE_VALUE_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_WHITE_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_XY_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_XY_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_XY_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ON_COMMAND_TYPE, default=DEFAULT_ON_COMMAND_TYPE):
        vol.In(VALUES_ON_COMMAND_TYPE),
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT light through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT light dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT light."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(light.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up a MQTT Light."""
    config.setdefault(
        CONF_STATE_VALUE_TEMPLATE, config.get(CONF_VALUE_TEMPLATE))

    async_add_entities([MqttLight(
        config.get(CONF_NAME),
        config.get(CONF_UNIQUE_ID),
        config.get(CONF_EFFECT_LIST),
        {
            key: config.get(key) for key in (
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
        },
        {
            CONF_BRIGHTNESS: config.get(CONF_BRIGHTNESS_VALUE_TEMPLATE),
            CONF_COLOR_TEMP: config.get(CONF_COLOR_TEMP_VALUE_TEMPLATE),
            CONF_EFFECT: config.get(CONF_EFFECT_VALUE_TEMPLATE),
            CONF_HS: config.get(CONF_HS_VALUE_TEMPLATE),
            CONF_RGB: config.get(CONF_RGB_VALUE_TEMPLATE),
            CONF_RGB_COMMAND_TEMPLATE: config.get(CONF_RGB_COMMAND_TEMPLATE),
            CONF_STATE: config.get(CONF_STATE_VALUE_TEMPLATE),
            CONF_WHITE_VALUE: config.get(CONF_WHITE_VALUE_TEMPLATE),
            CONF_XY: config.get(CONF_XY_VALUE_TEMPLATE),
        },
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        {
            'on': config.get(CONF_PAYLOAD_ON),
            'off': config.get(CONF_PAYLOAD_OFF),
        },
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_BRIGHTNESS_SCALE),
        config.get(CONF_WHITE_VALUE_SCALE),
        config.get(CONF_ON_COMMAND_TYPE),
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        discovery_hash,
    )])


class MqttLight(MqttAvailability, MqttDiscoveryUpdate, Light):
    """Representation of a MQTT light."""

    def __init__(self, name, unique_id, effect_list, topic, templates,
                 qos, retain, payload, optimistic, brightness_scale,
                 white_value_scale, on_command_type, availability_topic,
                 payload_available, payload_not_available, discovery_hash):
        """Initialize MQTT light."""
        MqttAvailability.__init__(self, availability_topic, qos,
                                  payload_available, payload_not_available)
        MqttDiscoveryUpdate.__init__(self, discovery_hash)
        self._name = name
        self._unique_id = unique_id
        self._effect_list = effect_list
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._payload = payload
        self._templates = templates
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._optimistic_rgb = \
            optimistic or topic[CONF_RGB_STATE_TOPIC] is None
        self._optimistic_brightness = (
            optimistic or
            (topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None and
             topic[CONF_BRIGHTNESS_STATE_TOPIC] is None) or
            (topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is None and
             topic[CONF_RGB_STATE_TOPIC] is None))
        self._optimistic_color_temp = (
            optimistic or topic[CONF_COLOR_TEMP_STATE_TOPIC] is None)
        self._optimistic_effect = (
            optimistic or topic[CONF_EFFECT_STATE_TOPIC] is None)
        self._optimistic_hs = \
            optimistic or topic[CONF_HS_STATE_TOPIC] is None
        self._optimistic_white_value = (
            optimistic or topic[CONF_WHITE_VALUE_STATE_TOPIC] is None)
        self._optimistic_xy = \
            optimistic or topic[CONF_XY_STATE_TOPIC] is None
        self._brightness_scale = brightness_scale
        self._white_value_scale = white_value_scale
        self._on_command_type = on_command_type
        self._state = False
        self._brightness = None
        self._hs = None
        self._color_temp = None
        self._effect = None
        self._white_value = None
        self._supported_features = 0
        self._supported_features |= (
            topic[CONF_RGB_COMMAND_TOPIC] is not None and
            (SUPPORT_COLOR | SUPPORT_BRIGHTNESS))
        self._supported_features |= (
            topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None and
            SUPPORT_BRIGHTNESS)
        self._supported_features |= (
            topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None and
            SUPPORT_COLOR_TEMP)
        self._supported_features |= (
            topic[CONF_EFFECT_COMMAND_TOPIC] is not None and
            SUPPORT_EFFECT)
        self._supported_features |= (
            topic[CONF_HS_COMMAND_TOPIC] is not None and SUPPORT_COLOR)
        self._supported_features |= (
            topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None and
            SUPPORT_WHITE_VALUE)
        self._supported_features |= (
            topic[CONF_XY_COMMAND_TOPIC] is not None and SUPPORT_COLOR)
        self._discovery_hash = discovery_hash

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await MqttAvailability.async_added_to_hass(self)
        await MqttDiscoveryUpdate.async_added_to_hass(self)

        templates = {}
        for key, tpl in list(self._templates.items()):
            if tpl is None:
                templates[key] = lambda value: value
            else:
                tpl.hass = self.hass
                templates[key] = tpl.async_render_with_possible_json_value

        last_state = await async_get_last_state(self.hass, self.entity_id)

        @callback
        def state_received(topic, payload, qos):
            """Handle new MQTT messages."""
            payload = templates[CONF_STATE](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty state message from '%s'", topic)
                return

            if payload == self._payload['on']:
                self._state = True
            elif payload == self._payload['off']:
                self._state = False
            self.async_schedule_update_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_STATE_TOPIC], state_received,
                self._qos)
        elif self._optimistic and last_state:
            self._state = last_state.state == STATE_ON

        @callback
        def brightness_received(topic, payload, qos):
            """Handle new MQTT messages for the brightness."""
            payload = templates[CONF_BRIGHTNESS](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty brightness message from '%s'",
                              topic)
                return

            device_value = float(payload)
            percent_bright = device_value / self._brightness_scale
            self._brightness = int(percent_bright * 255)
            self.async_schedule_update_ha_state()

        if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_BRIGHTNESS_STATE_TOPIC],
                brightness_received, self._qos)
            self._brightness = 255
        elif self._optimistic_brightness and last_state\
                and last_state.attributes.get(ATTR_BRIGHTNESS):
            self._brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
        elif self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            self._brightness = 255
        else:
            self._brightness = None

        @callback
        def rgb_received(topic, payload, qos):
            """Handle new MQTT messages for RGB."""
            payload = templates[CONF_RGB](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty rgb message from '%s'", topic)
                return

            rgb = [int(val) for val in payload.split(',')]
            self._hs = color_util.color_RGB_to_hs(*rgb)
            if self._topic[CONF_BRIGHTNESS_STATE_TOPIC] is None:
                percent_bright = \
                    float(color_util.color_RGB_to_hsv(*rgb)[2]) / 100.0
                self._brightness = int(percent_bright * 255)
            self.async_schedule_update_ha_state()

        if self._topic[CONF_RGB_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_RGB_STATE_TOPIC], rgb_received,
                self._qos)
            self._hs = (0, 0)
        if self._optimistic_rgb and last_state\
                and last_state.attributes.get(ATTR_HS_COLOR):
            self._hs = last_state.attributes.get(ATTR_HS_COLOR)
        elif self._topic[CONF_RGB_COMMAND_TOPIC] is not None:
            self._hs = (0, 0)

        @callback
        def color_temp_received(topic, payload, qos):
            """Handle new MQTT messages for color temperature."""
            payload = templates[CONF_COLOR_TEMP](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty color temp message from '%s'",
                              topic)
                return

            self._color_temp = int(payload)
            self.async_schedule_update_ha_state()

        if self._topic[CONF_COLOR_TEMP_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_COLOR_TEMP_STATE_TOPIC],
                color_temp_received, self._qos)
            self._color_temp = 150
        if self._optimistic_color_temp and last_state\
                and last_state.attributes.get(ATTR_COLOR_TEMP):
            self._color_temp = last_state.attributes.get(ATTR_COLOR_TEMP)
        elif self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None:
            self._color_temp = 150
        else:
            self._color_temp = None

        @callback
        def effect_received(topic, payload, qos):
            """Handle new MQTT messages for effect."""
            payload = templates[CONF_EFFECT](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty effect message from '%s'", topic)
                return

            self._effect = payload
            self.async_schedule_update_ha_state()

        if self._topic[CONF_EFFECT_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_EFFECT_STATE_TOPIC],
                effect_received, self._qos)
            self._effect = 'none'
        if self._optimistic_effect and last_state\
                and last_state.attributes.get(ATTR_EFFECT):
            self._effect = last_state.attributes.get(ATTR_EFFECT)
        elif self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None:
            self._effect = 'none'
        else:
            self._effect = None

        @callback
        def hs_received(topic, payload, qos):
            """Handle new MQTT messages for hs color."""
            payload = templates[CONF_HS](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty hs message from '%s'", topic)
                return

            try:
                hs_color = [float(val) for val in payload.split(',', 2)]
                self._hs = hs_color
                self.async_schedule_update_ha_state()
            except ValueError:
                _LOGGER.debug("Failed to parse hs state update: '%s'",
                              payload)

        if self._topic[CONF_HS_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_HS_STATE_TOPIC], hs_received,
                self._qos)
            self._hs = (0, 0)
        if self._optimistic_hs and last_state\
                and last_state.attributes.get(ATTR_HS_COLOR):
            self._hs = last_state.attributes.get(ATTR_HS_COLOR)
        elif self._topic[CONF_HS_COMMAND_TOPIC] is not None:
            self._hs = (0, 0)

        @callback
        def white_value_received(topic, payload, qos):
            """Handle new MQTT messages for white value."""
            payload = templates[CONF_WHITE_VALUE](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty white value message from '%s'",
                              topic)
                return

            device_value = float(payload)
            percent_white = device_value / self._white_value_scale
            self._white_value = int(percent_white * 255)
            self.async_schedule_update_ha_state()

        if self._topic[CONF_WHITE_VALUE_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_WHITE_VALUE_STATE_TOPIC],
                white_value_received, self._qos)
            self._white_value = 255
        elif self._optimistic_white_value and last_state\
                and last_state.attributes.get(ATTR_WHITE_VALUE):
            self._white_value = last_state.attributes.get(ATTR_WHITE_VALUE)
        elif self._topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None:
            self._white_value = 255
        else:
            self._white_value = None

        @callback
        def xy_received(topic, payload, qos):
            """Handle new MQTT messages for xy color."""
            payload = templates[CONF_XY](payload)
            if not payload:
                _LOGGER.debug("Ignoring empty xy-color message from '%s'",
                              topic)
                return

            xy_color = [float(val) for val in payload.split(',')]
            self._hs = color_util.color_xy_to_hs(*xy_color)
            self.async_schedule_update_ha_state()

        if self._topic[CONF_XY_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_XY_STATE_TOPIC], xy_received,
                self._qos)
            self._hs = (0, 0)
        if self._optimistic_xy and last_state\
                and last_state.attributes.get(ATTR_HS_COLOR):
            self._hs = last_state.attributes.get(ATTR_HS_COLOR)
        elif self._topic[CONF_XY_COMMAND_TOPIC] is not None:
            self._hs = (0, 0)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hs

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def white_value(self):
        """Return the white property."""
        return self._white_value

    @property
    def should_poll(self):
        """No polling needed for a MQTT light."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

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
        return self._effect_list

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False

        if self._on_command_type == 'first':
            mqtt.async_publish(
                self.hass, self._topic[CONF_COMMAND_TOPIC],
                self._payload['on'], self._qos, self._retain)
            should_update = True

        # If brightness is being used instead of an on command, make sure
        # there is a brightness input.  Either set the brightness to our
        # saved value or the maximum value if this is the first call
        elif self._on_command_type == 'brightness':
            if ATTR_BRIGHTNESS not in kwargs:
                kwargs[ATTR_BRIGHTNESS] = self._brightness if \
                                          self._brightness else 255

        if ATTR_HS_COLOR in kwargs and \
           self._topic[CONF_RGB_COMMAND_TOPIC] is not None:

            hs_color = kwargs[ATTR_HS_COLOR]

            # If there's a brightness topic set, we don't want to scale the RGB
            # values given using the brightness.
            if self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
                brightness = 255
            else:
                brightness = kwargs.get(
                    ATTR_BRIGHTNESS, self._brightness if self._brightness else
                    255)
            rgb = color_util.color_hsv_to_RGB(
                hs_color[0], hs_color[1], brightness / 255 * 100)
            tpl = self._templates[CONF_RGB_COMMAND_TEMPLATE]
            if tpl:
                rgb_color_str = tpl.async_render({
                    'red': rgb[0],
                    'green': rgb[1],
                    'blue': rgb[2],
                })
            else:
                rgb_color_str = '{},{},{}'.format(*rgb)

            mqtt.async_publish(
                self.hass, self._topic[CONF_RGB_COMMAND_TOPIC],
                rgb_color_str, self._qos, self._retain)

            if self._optimistic_rgb:
                self._hs = kwargs[ATTR_HS_COLOR]
                should_update = True

        if ATTR_HS_COLOR in kwargs and \
           self._topic[CONF_HS_COMMAND_TOPIC] is not None:

            hs_color = kwargs[ATTR_HS_COLOR]
            mqtt.async_publish(
                self.hass, self._topic[CONF_HS_COMMAND_TOPIC],
                '{},{}'.format(*hs_color), self._qos,
                self._retain)

            if self._optimistic_hs:
                self._hs = kwargs[ATTR_HS_COLOR]
                should_update = True

        if ATTR_HS_COLOR in kwargs and \
           self._topic[CONF_XY_COMMAND_TOPIC] is not None:

            xy_color = color_util.color_hs_to_xy(*kwargs[ATTR_HS_COLOR])
            mqtt.async_publish(
                self.hass, self._topic[CONF_XY_COMMAND_TOPIC],
                '{},{}'.format(*xy_color), self._qos,
                self._retain)

            if self._optimistic_xy:
                self._hs = kwargs[ATTR_HS_COLOR]
                should_update = True

        if ATTR_BRIGHTNESS in kwargs and \
           self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC] is not None:
            percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
            device_brightness = int(percent_bright * self._brightness_scale)
            mqtt.async_publish(
                self.hass, self._topic[CONF_BRIGHTNESS_COMMAND_TOPIC],
                device_brightness, self._qos, self._retain)

            if self._optimistic_brightness:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True
        elif ATTR_BRIGHTNESS in kwargs and ATTR_HS_COLOR not in kwargs and\
                self._topic[CONF_RGB_COMMAND_TOPIC] is not None:
            rgb = color_util.color_hsv_to_RGB(
                self._hs[0], self._hs[1], kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            tpl = self._templates[CONF_RGB_COMMAND_TEMPLATE]
            if tpl:
                rgb_color_str = tpl.async_render({
                    'red': rgb[0],
                    'green': rgb[1],
                    'blue': rgb[2],
                })
            else:
                rgb_color_str = '{},{},{}'.format(*rgb)

            mqtt.async_publish(
                self.hass, self._topic[CONF_RGB_COMMAND_TOPIC],
                rgb_color_str, self._qos, self._retain)

            if self._optimistic_brightness:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        if ATTR_COLOR_TEMP in kwargs and \
           self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC] is not None:
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            mqtt.async_publish(
                self.hass, self._topic[CONF_COLOR_TEMP_COMMAND_TOPIC],
                color_temp, self._qos, self._retain)

            if self._optimistic_color_temp:
                self._color_temp = kwargs[ATTR_COLOR_TEMP]
                should_update = True

        if ATTR_EFFECT in kwargs and \
           self._topic[CONF_EFFECT_COMMAND_TOPIC] is not None:
            effect = kwargs[ATTR_EFFECT]
            if effect in self._effect_list:
                mqtt.async_publish(
                    self.hass, self._topic[CONF_EFFECT_COMMAND_TOPIC],
                    effect, self._qos, self._retain)

                if self._optimistic_effect:
                    self._effect = kwargs[ATTR_EFFECT]
                    should_update = True

        if ATTR_WHITE_VALUE in kwargs and \
           self._topic[CONF_WHITE_VALUE_COMMAND_TOPIC] is not None:
            percent_white = float(kwargs[ATTR_WHITE_VALUE]) / 255
            device_white_value = int(percent_white * self._white_value_scale)
            mqtt.async_publish(
                self.hass, self._topic[CONF_WHITE_VALUE_COMMAND_TOPIC],
                device_white_value, self._qos, self._retain)

            if self._optimistic_white_value:
                self._white_value = kwargs[ATTR_WHITE_VALUE]
                should_update = True

        if self._on_command_type == 'last':
            mqtt.async_publish(self.hass, self._topic[CONF_COMMAND_TOPIC],
                               self._payload['on'], self._qos, self._retain)
            should_update = True

        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC], self._payload['off'],
            self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_schedule_update_ha_state()
