"""Support for the IKEA Tradfri platform."""

from homeassistant.components.tradfri import KEY_GATEWAY
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, ATTR_RGB_COLOR,
    SUPPORT_RGB_COLOR, PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA)
from homeassistant.util import color as color_util

DEPENDENCIES = ['tradfri']
SUPPORTED_FEATURES = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the IKEA Tradfri Light platform."""
    if discovery_info is None:
        return

    gateway_id = discovery_info['gateway']
    gateway = hass.data[KEY_GATEWAY][gateway_id]
    devices = gateway.get_devices()
    lights = [dev for dev in devices if dev.has_light_control]
    add_devices(Tradfri(light) for light in lights)


class Tradfri(Light):
    """The platform class required by hass."""

    def __init__(self, light):
        """Initialize a Light."""
        self._light = light

        # Caching of LightControl and light object
        self._light_control = light.light_control
        self._light_data = light.light_control.lights[0]
        self._name = light.name
        self._rgb_color = None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._light_data.state

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255)."""
        return self._light_data.dimmer

    @property
    def rgb_color(self):
        """RGB color of the light."""
        return self._rgb_color

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        return self._light_control.set_state(False)

    def turn_on(self, **kwargs):
        """
        Instruct the light to turn on.

        After adding "self._light_data.hexcolor is not None"
        for ATTR_RGB_COLOR, this also supports Philips Hue bulbs.
        """
        if ATTR_BRIGHTNESS in kwargs:
            self._light_control.set_dimmer(kwargs[ATTR_BRIGHTNESS])
        else:
            self._light_control.set_state(True)

        if ATTR_RGB_COLOR in kwargs and self._light_data.hex_color is not None:
            self._light.light_control.set_hex_color(
                color_util.color_rgb_to_hex(*kwargs[ATTR_RGB_COLOR]))

    def update(self):
        """Fetch new state data for this light."""
        self._light.update()

        # Handle Hue lights paired with the gatway
        if self._light_data.hex_color is not None:
            self._rgb_color = color_util.rgb_hex_to_rgb_list(
                self._light_data.hex_color)
