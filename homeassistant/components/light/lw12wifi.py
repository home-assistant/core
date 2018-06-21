"""
Support for Lagute LW-12 WiFi LED Controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lw12wifi/
"""

import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_HS_COLOR, ATTR_TRANSITION,
    Light, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, SUPPORT_EFFECT,
    SUPPORT_COLOR, SUPPORT_TRANSITION
)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util


REQUIREMENTS = ['lw12==0.9.2']

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = 'LW-12 FC'
DEFAULT_PORT = 5000

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup LW-12 WiFi LED Controller platform."""
    import lw12

    # Assign configuration variables.
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    # Add devices
    lw12_light = lw12.LW12Controller(host, port)
    add_devices([LW12WiFi(name, lw12_light)])


class LW12WiFi(Light):
    """LW-12 WiFi LED Controller."""

    def __init__(self, name, lw12_light):
        """Initialisation of LW-12 WiFi LED Controller.

        Args:
            name: Friendly name for this platform to use.
            lw12_light: Instance of the LW12 controller.
        """
        self._light = lw12_light
        self._name = name
        self._state = None
        self._effect = None
        self._rgb_color = [255, 255, 255]
        self._brightness = 255
        # Setup feature list
        self._supported_features = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT \
            | SUPPORT_COLOR | SUPPORT_TRANSITION

    @property
    def name(self):
        """Return the display name of the controlled light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

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

    @property
    def shoud_poll(self) -> bool:
        """Return False to not poll the state of this entity."""
        return False

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        import lw12
        self._light.light_on()
        if ATTR_HS_COLOR in kwargs:
            self._rgb_color = color_util.color_hs_to_RGB(
                *kwargs[ATTR_HS_COLOR])
            self._light.set_color(*self._rgb_color)
            self._effect = None
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs.get(ATTR_BRIGHTNESS)
            brightness = int(self._brightness / 255 * 100)
            self._light.set_light_option(lw12.LW12_LIGHT.BRIGHTNESS,
                                         brightness)
        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT].replace(' ', '_').upper()
            # Check if a known and supported effect was selected.
            if self._effect in [eff.name for eff in lw12.LW12_EFFECT]:
                # Selected effect is supported and will be applied.
                self._light.set_effect(lw12.LW12_EFFECT[self._effect])
            else:
                # Unknown effect was set, recover by disabling the effect
                # mode and log an error.
                _LOGGER.error("Unknown effect selected: %s", self._effect)
                self._effect = None
        if ATTR_TRANSITION in kwargs:
            transition_speed = int(kwargs[ATTR_TRANSITION])
            self._light.set_light_option(lw12.LW12_LIGHT.FLASH,
                                         transition_speed)
        self._state = True

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.light_off()
        self._state = False
