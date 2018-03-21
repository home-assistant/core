"""
Support for Lagute LW-12 WiFi LED Controller.

Configuration example:

light:
  - platform: lw12wifi
    # Host name or IP of LW-12 LED stripe to control
    host: 192.168.0.1
    # (Optional) Some firmware versions of the LW-12 controller listen
    # on different ports.
    port: 5000
    # (Optional) Friendly name
    name: LW-12 FC
    # (Optional) Effect to use as default (Default=None).
    # For a full list of supported effects see:
    # https://github.com/jaypikay/python-lw12/blob/v0.9.2/lw12.py#L54
    effect: "Gradient Cyan"
    # (Optional) Transition speed for effects (Value: 0-255)
    transition: 10
    # (Optional) LED Brightness (Value: 0-255)
    brightness: 10
    # (Optional) RGB value array as standard color to set.
    # This option is is ignored when effect is set.
    rgb: [255, 255, 255]
"""

import logging
import time

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_HS_COLOR, ATTR_TRANSITION,
    Light, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, SUPPORT_EFFECT,
    SUPPORT_COLOR, SUPPORT_TRANSITION
)
from homeassistant.const import (
    CONF_BRIGHTNESS, CONF_EFFECT, CONF_HOST, CONF_NAME, CONF_PORT, CONF_RGB
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util


REQUIREMENTS = ['lw12==0.9.2']

_LOGGER = logging.getLogger(__name__)

CONF_TRANSITION = 'transition'

DEFAULT_NAME = 'LW-12 FC'
DEFAULT_PORT = 5000
DEFAULT_RGB = [255, 255, 255]
DEFAULT_BRIGHTNESS = 255
DEFAULT_EFFECT = None
DEFAULT_TRANSITION = 128

DOMAIN = 'lw12wifi'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_RGB, default=DEFAULT_RGB):
        vol.All(list, vol.Length(min=3, max=3),
                [vol.All(vol.Coerce(int), vol.Range(min=0, max=255))]),
    vol.Optional(CONF_BRIGHTNESS, default=DEFAULT_BRIGHTNESS):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup LW-12 WiFi LED Controller platform."""
    # Assign configuration variables.
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    rgb = config.get(CONF_RGB)
    brightness = config.get(CONF_BRIGHTNESS)
    effect = config.get(CONF_EFFECT)
    transition = config.get(CONF_TRANSITION)
    # Add devices
    add_devices([LW12WiFi(name, host, port, rgb, brightness, effect,
                          transition)])


class LW12WiFi(Light):
    """LW-12 WiFi LED Controller."""

    def __init__(self, name, host, port, rgb_color, brightness, effect,
                 transition):
        """Initialisation of LW-12 WiFi LED Controller.

        Args:
            name: Friendly name for this platform to use.
            host: Hostname or IP address of the device.
            port: Port (Default: 5000) to connect to.
            rgb_color: Initial color to set after the light turned on.
            brightness: Brightness of the LEDs to set.
            effect: If not None, turn on the lights with the selected effect.
            transition: Speed of the effects.
        """
        import lw12

        self._light = lw12.LW12Controller(host, port)
        self._name = name
        self._host = host
        self._port = port
        self._rgb_color = rgb_color
        self._brightness = brightness
        self._state = None
        self._effect = effect
        self._transition_speed = transition
        # Setup feature list
        self._supported_features = SUPPORT_BRIGHTNESS
        self._supported_features |= SUPPORT_EFFECT
        self._supported_features |= SUPPORT_COLOR
        self._supported_features |= SUPPORT_TRANSITION

    @property
    def name(self):
        """Return the display name of the controlled light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def rgb_color(self):
        """Read back the color of the light.

        Returns [r, g, b] list with values in range of 0-255.
        """
        return self._rgb_color

    @property
    def hs_color(self):
        """Read back the hue-saturation of the light."""
        return color_util.color_RGB_to_hs(*self._rgb_color)

    @property
    def effect(self):
        """Return current light effect."""
        if self._effect is None:
            return None
        return self._effect.replace('_', ' ').title()

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Return a list of supported features."""
        return self._supported_features

    @property
    def effect_list(self):
        """Return a list of available effects.

        Use the Enum element name for display.
        """
        import lw12
        return [effect.name.replace('_', ' ').title()
                for effect in lw12.LW12_EFFECT]

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        import lw12
        self._light.light_on()
        if self._effect is not None:
            if self._effect.replace(' ', '_').upper() in lw12.LW12_EFFECT:
                kwargs['effect'] = self._effect
            else:
                # Unknown effect, changing to no selected effect.
                self._effect = None
        if ATTR_HS_COLOR in kwargs:
            self._rgb_color = color_util.color_hs_to_RGB(
                *kwargs.get(ATTR_HS_COLOR))
            self._light.set_color(*self._rgb_color)
            self._effect = None
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs.get(ATTR_BRIGHTNESS)
            brightness = int(self._brightness / 255 * 100)
            self._light.set_light_option(lw12.LW12_LIGHT.BRIGHTNESS,
                                         brightness)
        if ATTR_EFFECT in kwargs:
            self._effect = kwargs.get(ATTR_EFFECT).replace(' ', '_').upper()
            self._light.set_effect(lw12.LW12_EFFECT[self._effect])
            # Sending UDP messages to quickly after the previous message
            # the new command is ignored. Adding a short wait time.
            time.sleep(.25)
            self._light.set_light_option(lw12.LW12_LIGHT.FLASH,
                                         self._transition_speed)
        if ATTR_TRANSITION in kwargs:
            self._transition_speed = int(kwargs[ATTR_TRANSITION])
            self._light.set_light_option(lw12.LW12_LIGHT.FLASH,
                                         self._transition_speed)
        self._state = True

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.light_off()
        self._state = False
