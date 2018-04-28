"""
Support for MQTT JSON lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt_json/
"""
import logging
import json
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH,
    ATTR_TRANSITION, ATTR_WHITE_VALUE, ATTR_HS_COLOR,
    FLASH_LONG, FLASH_SHORT, Light, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH, SUPPORT_COLOR,
    SUPPORT_TRANSITION, SUPPORT_WHITE_VALUE)
from homeassistant.components.light.mqtt import CONF_BRIGHTNESS_SCALE
from homeassistant.const import (
    CONF_BRIGHTNESS, CONF_COLOR_TEMP, CONF_EFFECT,
    CONF_NAME, CONF_OPTIMISTIC, CONF_RGB, CONF_WHITE_VALUE, CONF_XY)
from homeassistant.components.mqtt import (
    CONF_AVAILABILITY_TOPIC, CONF_STATE_TOPIC, CONF_COMMAND_TOPIC,
    CONF_PAYLOAD_AVAILABLE, CONF_PAYLOAD_NOT_AVAILABLE, CONF_QOS, CONF_RETAIN,
    MqttAvailability)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mqtt_json'

DEPENDENCIES = ['mqtt']

DEFAULT_BRIGHTNESS = False
DEFAULT_COLOR_TEMP = False
DEFAULT_EFFECT = False
DEFAULT_FLASH_TIME_LONG = 10
DEFAULT_FLASH_TIME_SHORT = 2
DEFAULT_NAME = 'MQTT JSON Light'
DEFAULT_OPTIMISTIC = False
DEFAULT_RGB = False
DEFAULT_WHITE_VALUE = False
DEFAULT_XY = False
DEFAULT_HS = False
DEFAULT_BRIGHTNESS_SCALE = 255

CONF_EFFECT_LIST = 'effect_list'

CONF_FLASH_TIME_LONG = 'flash_time_long'
CONF_FLASH_TIME_SHORT = 'flash_time_short'
CONF_HS = 'hs'

# Stealing some of these from the base MQTT configs.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
    vol.Optional(CONF_BRIGHTNESS_SCALE, default=DEFAULT_BRIGHTNESS_SCALE):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_COLOR_TEMP, default=DEFAULT_COLOR_TEMP): cv.boolean,
    vol.Optional(CONF_EFFECT, default=DEFAULT_EFFECT): cv.boolean,
    vol.Optional(CONF_EFFECT_LIST): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT):
        cv.positive_int,
    vol.Optional(CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG):
        cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_QOS, default=mqtt.DEFAULT_QOS):
        vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    vol.Optional(CONF_RGB, default=DEFAULT_RGB): cv.boolean,
    vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_WHITE_VALUE, default=DEFAULT_WHITE_VALUE): cv.boolean,
    vol.Optional(CONF_XY, default=DEFAULT_XY): cv.boolean,
    vol.Optional(CONF_HS, default=DEFAULT_HS): cv.boolean,
    vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
}).extend(mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_devices, discovery_info=None):
    """Set up a MQTT JSON Light."""
    if discovery_info is not None:
        config = PLATFORM_SCHEMA(discovery_info)
    async_add_devices([MqttJson(
        config.get(CONF_NAME),
        config.get(CONF_EFFECT_LIST),
        {
            key: config.get(key) for key in (
                CONF_STATE_TOPIC,
                CONF_COMMAND_TOPIC
            )
        },
        config.get(CONF_QOS),
        config.get(CONF_RETAIN),
        config.get(CONF_OPTIMISTIC),
        config.get(CONF_BRIGHTNESS),
        config.get(CONF_COLOR_TEMP),
        config.get(CONF_EFFECT),
        config.get(CONF_RGB),
        config.get(CONF_WHITE_VALUE),
        config.get(CONF_XY),
        config.get(CONF_HS),
        {
            key: config.get(key) for key in (
                CONF_FLASH_TIME_SHORT,
                CONF_FLASH_TIME_LONG
            )
        },
        config.get(CONF_AVAILABILITY_TOPIC),
        config.get(CONF_PAYLOAD_AVAILABLE),
        config.get(CONF_PAYLOAD_NOT_AVAILABLE),
        config.get(CONF_BRIGHTNESS_SCALE)
    )])


class MqttJson(MqttAvailability, Light):
    """Representation of a MQTT JSON light."""

    def __init__(self, name, effect_list, topic, qos, retain, optimistic,
                 brightness, color_temp, effect, rgb, white_value, xy, hs,
                 flash_times, availability_topic, payload_available,
                 payload_not_available, brightness_scale):
        """Initialize MQTT JSON light."""
        super().__init__(availability_topic, qos, payload_available,
                         payload_not_available)
        self._name = name
        self._effect_list = effect_list
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._state = False
        self._rgb = rgb
        self._xy = xy
        self._hs_support = hs
        if brightness:
            self._brightness = 255
        else:
            self._brightness = None

        if color_temp:
            self._color_temp = 150
        else:
            self._color_temp = None

        if effect:
            self._effect = 'none'
        else:
            self._effect = None

        if hs or rgb or xy:
            self._hs = [0, 0]
        else:
            self._hs = None

        if white_value:
            self._white_value = 255
        else:
            self._white_value = None

        self._flash_times = flash_times
        self._brightness_scale = brightness_scale

        self._supported_features = (SUPPORT_TRANSITION | SUPPORT_FLASH)
        self._supported_features |= (rgb and SUPPORT_COLOR)
        self._supported_features |= (brightness and SUPPORT_BRIGHTNESS)
        self._supported_features |= (color_temp and SUPPORT_COLOR_TEMP)
        self._supported_features |= (effect and SUPPORT_EFFECT)
        self._supported_features |= (white_value and SUPPORT_WHITE_VALUE)
        self._supported_features |= (xy and SUPPORT_COLOR)
        self._supported_features |= (hs and SUPPORT_COLOR)

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()

        @callback
        def state_received(topic, payload, qos):
            """Handle new MQTT messages."""
            values = json.loads(payload)

            if values['state'] == 'ON':
                self._state = True
            elif values['state'] == 'OFF':
                self._state = False

            if self._hs is not None:
                try:
                    red = int(values['color']['r'])
                    green = int(values['color']['g'])
                    blue = int(values['color']['b'])

                    self._hs = color_util.color_RGB_to_hs(red, green, blue)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid RGB color value received")

                try:
                    x_color = float(values['color']['x'])
                    y_color = float(values['color']['y'])

                    self._hs = color_util.color_xy_to_hs(x_color, y_color)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid XY color value received")

                try:
                    hue = float(values['color']['h'])
                    saturation = float(values['color']['s'])

                    self._hs = (hue, saturation)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid HS color value received")

            if self._brightness is not None:
                try:
                    self._brightness = int(values['brightness'] /
                                           float(self._brightness_scale) *
                                           255)
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid brightness value received")

            if self._color_temp is not None:
                try:
                    self._color_temp = int(values['color_temp'])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid color temp value received")

            if self._effect is not None:
                try:
                    self._effect = values['effect']
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid effect value received")

            if self._white_value is not None:
                try:
                    self._white_value = int(values['white_value'])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid white value received")

            self.async_schedule_update_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            await mqtt.async_subscribe(
                self.hass, self._topic[CONF_STATE_TOPIC], state_received,
                self._qos)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hs

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
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        should_update = False

        message = {'state': 'ON'}

        if ATTR_HS_COLOR in kwargs and (self._hs_support
                                        or self._rgb or self._xy):
            hs_color = kwargs[ATTR_HS_COLOR]
            message['color'] = {}
            if self._rgb:
                brightness = kwargs.get(
                    ATTR_BRIGHTNESS,
                    self._brightness if self._brightness else 255)
                rgb = color_util.color_hsv_to_RGB(
                    hs_color[0], hs_color[1], brightness / 255 * 100)
                message['color']['r'] = rgb[0]
                message['color']['g'] = rgb[1]
                message['color']['b'] = rgb[2]
            if self._xy:
                xy_color = color_util.color_hs_to_xy(*kwargs[ATTR_HS_COLOR])
                message['color']['x'] = xy_color[0]
                message['color']['y'] = xy_color[1]
            if self._hs_support:
                message['color']['h'] = hs_color[0]
                message['color']['s'] = hs_color[1]

            if self._optimistic:
                self._hs = kwargs[ATTR_HS_COLOR]
                should_update = True

        if ATTR_FLASH in kwargs:
            flash = kwargs.get(ATTR_FLASH)

            if flash == FLASH_LONG:
                message['flash'] = self._flash_times[CONF_FLASH_TIME_LONG]
            elif flash == FLASH_SHORT:
                message['flash'] = self._flash_times[CONF_FLASH_TIME_SHORT]

        if ATTR_TRANSITION in kwargs:
            message['transition'] = int(kwargs[ATTR_TRANSITION])

        if ATTR_BRIGHTNESS in kwargs:
            message['brightness'] = int(kwargs[ATTR_BRIGHTNESS] /
                                        float(DEFAULT_BRIGHTNESS_SCALE) *
                                        self._brightness_scale)

            if self._optimistic:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        if ATTR_COLOR_TEMP in kwargs:
            message['color_temp'] = int(kwargs[ATTR_COLOR_TEMP])

            if self._optimistic:
                self._color_temp = kwargs[ATTR_COLOR_TEMP]
                should_update = True

        if ATTR_EFFECT in kwargs:
            message['effect'] = kwargs[ATTR_EFFECT]

            if self._optimistic:
                self._effect = kwargs[ATTR_EFFECT]
                should_update = True

        if ATTR_WHITE_VALUE in kwargs:
            message['white_value'] = int(kwargs[ATTR_WHITE_VALUE])

            if self._optimistic:
                self._white_value = kwargs[ATTR_WHITE_VALUE]
                should_update = True

        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC], json.dumps(message),
            self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        message = {'state': 'OFF'}

        if ATTR_TRANSITION in kwargs:
            message['transition'] = int(kwargs[ATTR_TRANSITION])

        mqtt.async_publish(
            self.hass, self._topic[CONF_COMMAND_TOPIC], json.dumps(message),
            self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = False
            self.async_schedule_update_ha_state()
