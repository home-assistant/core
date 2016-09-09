"""
Support for MQTT JSON lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt_json/
"""

import logging
import json
import voluptuous as vol

import homeassistant.components.mqtt as mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_TRANSITION, PLATFORM_SCHEMA,
    ATTR_FLASH, FLASH_LONG, FLASH_SHORT, SUPPORT_BRIGHTNESS, SUPPORT_FLASH,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, Light)
from homeassistant.const import (
    CONF_NAME, CONF_OPTIMISTIC, CONF_BRIGHTNESS, CONF_RGB)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mqtt_json'

DEPENDENCIES = ['mqtt']

DEFAULT_NAME = 'MQTT JSON Light'
DEFAULT_OPTIMISTIC = False
DEFAULT_BRIGHTNESS = False
DEFAULT_RGB = False
DEFAULT_FLASH_TIME_SHORT = 2
DEFAULT_FLASH_TIME_LONG = 10

CONF_FLASH_TIME_SHORT = 'flash_time_short'
CONF_FLASH_TIME_LONG = 'flash_time_long'

SUPPORT_MQTT_JSON = (SUPPORT_BRIGHTNESS | SUPPORT_FLASH | SUPPORT_RGB_COLOR |
                     SUPPORT_TRANSITION)

# Stealing some of these from the base MQTT configs.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_QOS, default=mqtt.DEFAULT_QOS):
        vol.All(vol.Coerce(int), vol.In([0, 1, 2])),
    vol.Required(CONF_COMMAND_TOPIC): mqtt.valid_publish_topic,
    vol.Optional(CONF_RETAIN, default=mqtt.DEFAULT_RETAIN): cv.boolean,
    vol.Optional(CONF_STATE_TOPIC): mqtt.valid_subscribe_topic,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS): cv.boolean,
    vol.Optional(CONF_RGB, default=DEFAULT_RGB): cv.boolean,
    vol.Optional(CONF_FLASH_TIME_SHORT, default=DEFAULT_FLASH_TIME_SHORT):
        cv.positive_int,
    vol.Optional(CONF_FLASH_TIME_LONG, default=DEFAULT_FLASH_TIME_LONG):
        cv.positive_int
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup a MQTT JSON Light."""
    add_devices([MqttJson(
        hass,
        config.get(CONF_NAME),
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
        config.get(CONF_RGB),
        {
            key: config.get(key) for key in (
                CONF_FLASH_TIME_SHORT,
                CONF_FLASH_TIME_LONG
            )
        }
    )])


class MqttJson(Light):
    """Representation of a MQTT JSON light."""

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    def __init__(self, hass, name, topic, qos, retain,
                 optimistic, brightness, rgb, flash_times):
        """Initialize MQTT JSON light."""
        self._hass = hass
        self._name = name
        self._topic = topic
        self._qos = qos
        self._retain = retain
        self._optimistic = optimistic or topic[CONF_STATE_TOPIC] is None
        self._state = False
        if brightness:
            self._brightness = 255
        else:
            self._brightness = None

        if rgb:
            self._rgb = [0, 0, 0]
        else:
            self._rgb = None

        self._flash_times = flash_times

        def state_received(topic, payload, qos):
            """A new MQTT message has been received."""
            values = json.loads(payload)

            if values['state'] == 'ON':
                self._state = True
            elif values['state'] == 'OFF':
                self._state = False

            if self._rgb is not None:
                try:
                    red = int(values['color']['r'])
                    green = int(values['color']['g'])
                    blue = int(values['color']['b'])

                    self._rgb = [red, green, blue]
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning("Invalid color value received")

            if self._brightness is not None:
                try:
                    self._brightness = int(values['brightness'])
                except KeyError:
                    pass
                except ValueError:
                    _LOGGER.warning('Invalid brightness value received')

            self.update_ha_state()

        if self._topic[CONF_STATE_TOPIC] is not None:
            mqtt.subscribe(self._hass, self._topic[CONF_STATE_TOPIC],
                           state_received, self._qos)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the RGB color value."""
        return self._rgb

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

    def turn_on(self, **kwargs):
        """Turn the device on."""
        should_update = False

        message = {'state': 'ON'}

        if ATTR_RGB_COLOR in kwargs:
            message['color'] = {
                'r': kwargs[ATTR_RGB_COLOR][0],
                'g': kwargs[ATTR_RGB_COLOR][1],
                'b': kwargs[ATTR_RGB_COLOR][2]
            }

            if self._optimistic:
                self._rgb = kwargs[ATTR_RGB_COLOR]
                should_update = True

        if ATTR_FLASH in kwargs:
            flash = kwargs.get(ATTR_FLASH)

            if flash == FLASH_LONG:
                message['flash'] = self._flash_times[CONF_FLASH_TIME_LONG]
            elif flash == FLASH_SHORT:
                message['flash'] = self._flash_times[CONF_FLASH_TIME_SHORT]

        if ATTR_TRANSITION in kwargs:
            message['transition'] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs:
            message['brightness'] = int(kwargs[ATTR_BRIGHTNESS])

            if self._optimistic:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                should_update = True

        mqtt.publish(self._hass, self._topic[CONF_COMMAND_TOPIC],
                     json.dumps(message), self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = True
            should_update = True

        if should_update:
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        message = {'state': 'OFF'}

        if ATTR_TRANSITION in kwargs:
            message['transition'] = kwargs[ATTR_TRANSITION]

        mqtt.publish(self._hass, self._topic[CONF_COMMAND_TOPIC],
                     json.dumps(message), self._qos, self._retain)

        if self._optimistic:
            # Optimistically assume that the light has changed state.
            self._state = False
            self.update_ha_state()
