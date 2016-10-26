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
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['lightify==1.0.3']

_LOGGER = logging.getLogger(__name__)

TEMP_MIN = 2000  # lightify minimum temperature
TEMP_MAX = 6500  # lightify maximum temperature
TEMP_MIN_HASS = 154  # home assistant minimum temperature
TEMP_MAX_HASS = 500  # home assistant maximum temperature
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

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._light.name()

    @property
    def rgb_color(self):
        """Last RGB color value set."""
        return self._light.rgb()

    @property
    def color_temp(self):
        """Return the color temperature."""
        o_temp = self._light.temp()
        temperature = int(TEMP_MIN_HASS + (TEMP_MAX_HASS - TEMP_MIN_HASS) *
                          (o_temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN))
        return temperature

    @property
    def brightness(self):
        """Brightness of this light between 0..255."""
        return int(self._light.lum() * 2.55)

    @property
    def is_on(self):
        """Update Status to True if device is on."""
        self.update_lights()
        _LOGGER.debug("is_on light state for light: %s is: %s",
                      self._light.name(), self._light.on())
        return self._light.on()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OSRAMLIGHTIFY

    def turn_on(self, **kwargs):
        """Turn the device on."""
        brightness = 100
        if self.brightness:
            brightness = int(self.brightness / 2.55)

        if ATTR_TRANSITION in kwargs:
            fade = kwargs[ATTR_TRANSITION] * 10
        else:
            fade = 0

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            self._light.set_rgb(red, green, blue, fade)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 2.55)

        if ATTR_COLOR_TEMP in kwargs:
            color_t = kwargs[ATTR_COLOR_TEMP]
            kelvin = int(((TEMP_MAX - TEMP_MIN) * (color_t - TEMP_MIN_HASS) /
                          (TEMP_MAX_HASS - TEMP_MIN_HASS)) + TEMP_MIN)
            self._light.set_temperature(kelvin, fade)

        effect = kwargs.get(ATTR_EFFECT)
        if effect == EFFECT_RANDOM:
            self._light.set_rgb(random.randrange(0, 255),
                                random.randrange(0, 255),
                                random.randrange(0, 255),
                                fade)

        self._light.set_luminance(brightness, fade)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if ATTR_TRANSITION in kwargs:
            fade = kwargs[ATTR_TRANSITION] * 10
        else:
            fade = 0
        self._light.set_luminance(0, fade)
        self.update_ha_state()

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)
