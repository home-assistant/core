"""
Support for Nanoleaf Aurora platform.

Based in large parts upon Software-2's ha-aurora and fully
reliant on Software-2's nanoleaf-aurora Python Library, see
https://github.com/software-2/ha-aurora as well as
https://github.com/software-2/nanoleaf

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.nanoleaf_aurora/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_RGB_COLOR,
    SUPPORT_EFFECT, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP,
    SUPPORT_RGB_COLOR, PLATFORM_SCHEMA, Light)
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.util import color as color_util
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin

REQUIREMENTS = ['nanoleaf==0.4.1']

SUPPORT_AURORA = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT |
                  SUPPORT_RGB_COLOR)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default='Aurora'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Nanoleaf Aurora device."""
    from nanoleaf import Aurora
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    aurora_light = Aurora(host, token)
    aurora_light.hass_name = name

    if aurora_light.on is None:
        _LOGGER.error("Could not connect to \
        Nanoleaf Aurora: %s on %s", name, host)
    add_devices([AuroraLight(aurora_light)])


class AuroraLight(Light):
    """Representation of a Nanoleaf Aurora."""

    def __init__(self, light):
        """Initialize an Aurora."""
        self._brightness = light.brightness
        self._color_temp = light.color_temperature
        self._effect = light.effect
        self._effects_list = light.effects_list
        self._light = light
        self._name = light.hass_name
        self._rgb_color = light.rgb
        self._state = light.on

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self._brightness is not None:
            return int(self._brightness * 2.55)
        return None

    @property
    def color_temp(self):
        """Return the current color temperature."""
        if self._color_temp is not None:
            return color_util.color_temperature_kelvin_to_mired(
                self._color_temp)
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effects_list

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:triangle-outline"

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def rgb_color(self):
        """Return the color in RGB."""
        return self._rgb_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_AURORA

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._light.on = True
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)
        effect = kwargs.get(ATTR_EFFECT)

        if rgb_color:
            self._light.rgb = rgb_color
            # Aurora API automatically sets scene to 100 brightness
            # This is to make sure that old brightness values are kept
            # If brightness is also set in the same call, the value will
            # be overwritten in a later block
            self._light.brightness = self._brightness

        if color_temp_mired:
            self._light.color_temperature = mired_to_kelvin(color_temp_mired)
        if brightness:
            self._light.brightness = int(brightness / 2.55)
        if effect:
            self._light.effect = effect

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.on = False

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._brightness = self._light.brightness
        self._color_temp = self._light.color_temperature
        self._effect = self._light.effect
        self._effects_list = self._light.effects_list
        self._rgb_color = self._light.rgb
        self._state = self._light.on
