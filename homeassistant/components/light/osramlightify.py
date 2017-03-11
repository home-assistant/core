"""
Support for Osram Lightify.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.osramlightify/
"""
import logging
import socket
import random
from datetime import timedelta

import voluptuous as vol

from homeassistant import util
from homeassistant.const import CONF_HOST
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_RGB_COLOR,
    ATTR_TRANSITION, EFFECT_RANDOM, SUPPORT_BRIGHTNESS, SUPPORT_EFFECT,
    SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, PLATFORM_SCHEMA)
from homeassistant.util.color import (
    color_temperature_mired_to_kelvin, color_temperature_kelvin_to_mired)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/tfriedel/python-lightify/archive/'
                'd6eadcf311e6e21746182d1480e97b350dda2b3e.zip#lightify==1.0.4']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

SUPPORT_OSRAMLIGHTIFY = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                         SUPPORT_EFFECT | SUPPORT_RGB_COLOR |
                         SUPPORT_TRANSITION)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Osram Lightify lights."""
    import lightify
    host = config.get(CONF_HOST)
    if host:
        try:
            bridge = lightify.Lightify(host)
        except socket.error as err:
            msg = 'Error connecting to bridge: {} due to: {}'.format(host,
                                                                     str(err))
            _LOGGER.exception(msg)
            return False
        setup_bridge(bridge, add_devices)
    else:
        _LOGGER.error('No host found in configuration')
        return False


def setup_bridge(bridge, add_devices_callback):
    """Setup the Lightify bridge."""
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """Update the lights objects with latest info from bridge."""
        bridge.update_all_light_status()

        new_lights = []

        for (light_id, light) in bridge.lights().items():
            if light_id not in lights:
                osram_light = OsramLightifyLight(light_id, light,
                                                 update_lights)

                lights[light_id] = osram_light
                new_lights.append(osram_light)
            else:
                lights[light_id].light = light

        if new_lights:
            add_devices_callback(new_lights)

    update_lights()


class OsramLightifyLight(Light):
    """Representation of an Osram Lightify Light."""

    def __init__(self, light_id, light, update_lights):
        """Initialize the light."""
        self._light = light
        self._light_id = light_id
        self.update_lights = update_lights
        self._brightness = None
        self._rgb = None
        self._name = None
        self._temperature = None
        self._state = False
        self.update()

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def rgb_color(self):
        """Last RGB color value set."""
        _LOGGER.debug("rgb_color light state for light: %s is: %s %s %s ",
                      self._name, self._rgb[0], self._rgb[1], self._rgb[2])
        return self._rgb

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._temperature

    @property
    def brightness(self):
        """Brightness of this light between 0..255."""
        _LOGGER.debug("brightness for light %s is: %s",
                      self._name, self._brightness)
        return self._brightness

    @property
    def is_on(self):
        """Update Status to True if device is on."""
        _LOGGER.debug("is_on light state for light: %s is: %s",
                      self._name, self._state)
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OSRAMLIGHTIFY

    def turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.debug("turn_on Attempting to turn on light: %s ",
                      self._name)

        self._light.set_onoff(1)
        self._state = self._light.on()

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION] * 10)
            _LOGGER.debug("turn_on requested transition time for light:"
                          " %s is: %s ",
                          self._name, transition)
        else:
            transition = 0
            _LOGGER.debug("turn_on requested transition time for light:"
                          " %s is: %s ",
                          self._name, transition)

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            _LOGGER.debug("turn_on requested ATTR_RGB_COLOR for light:"
                          " %s is: %s %s %s ",
                          self._name, red, green, blue)
            self._light.set_rgb(red, green, blue, transition)

        if ATTR_COLOR_TEMP in kwargs:
            color_t = kwargs[ATTR_COLOR_TEMP]
            kelvin = int(color_temperature_mired_to_kelvin(color_t))
            _LOGGER.debug("turn_on requested set_temperature for light:"
                          " %s: %s ", self._name, kelvin)
            self._light.set_temperature(kelvin, transition)

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            _LOGGER.debug("turn_on requested brightness for light: %s is: %s ",
                          self._name, self._brightness)
            self._brightness = self._light.set_luminance(
                int(self._brightness / 2.55),
                transition)

        if ATTR_EFFECT in kwargs:
            effect = kwargs.get(ATTR_EFFECT)
            if effect == EFFECT_RANDOM:
                self._light.set_rgb(random.randrange(0, 255),
                                    random.randrange(0, 255),
                                    random.randrange(0, 255),
                                    transition)
                _LOGGER.debug("turn_on requested random effect for light:"
                              " %s with transition %s ",
                              self._name, transition)

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("turn_off Attempting to turn off light: %s ",
                      self._name)
        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION] * 10)
            _LOGGER.debug("turn_off requested transition time for light:"
                          " %s is: %s ",
                          self._name, transition)
            self._light.set_luminance(0, transition)
        else:
            transition = 0
            _LOGGER.debug("turn_off requested transition time for light:"
                          " %s is: %s ",
                          self._name, transition)
            self._light.set_onoff(0)
            self._state = self._light.on()

        self.schedule_update_ha_state()

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)
        self._brightness = int(self._light.lum() * 2.55)
        self._name = self._light.name()
        self._rgb = self._light.rgb()
        o_temp = self._light.temp()
        self._temperature = color_temperature_kelvin_to_mired(o_temp)
        self._state = self._light.on()
