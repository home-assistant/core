"""
Demo light platform that implements lights.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import random

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT,
    ATTR_RGB_COLOR, ATTR_WHITE_VALUE, ATTR_XY_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_RGB_COLOR, SUPPORT_WHITE_VALUE,
    Light)

LIGHT_COLORS = [
    [237, 224, 33],
    [255, 63, 111],
]

LIGHT_EFFECT_LIST = ['rainbow', 'none']

LIGHT_TEMPS = [240, 380]

SUPPORT_DEMO = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT |
                SUPPORT_RGB_COLOR | SUPPORT_WHITE_VALUE)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the demo light platform."""
    add_devices_callback([
        DemoLight("Bed Light", False, True, effect_list=LIGHT_EFFECT_LIST,
                  effect=LIGHT_EFFECT_LIST[0]),
        DemoLight("Ceiling Lights", True, True,
                  LIGHT_COLORS[0], LIGHT_TEMPS[1]),
        DemoLight("Kitchen Lights", True, True,
                  LIGHT_COLORS[1], LIGHT_TEMPS[0])
    ])


class DemoLight(Light):
    """Representation of a demo light."""

    def __init__(self, name, state, available=False, rgb=None, ct=None,
                 brightness=180, xy_color=(.5, .5), white=200,
                 effect_list=None, effect=None):
        """Initialize the light."""
        self._name = name
        self._state = state
        self._rgb = rgb
        self._ct = ct or random.choice(LIGHT_TEMPS)
        self._brightness = brightness
        self._xy_color = xy_color
        self._white = white
        self._effect_list = effect_list
        self._effect = effect

    @property
    def should_poll(self) -> bool:
        """No polling needed for a demo light."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the light if any."""
        return self._name

    @property
    def available(self) -> bool:
        """Return availability."""
        # This demo light is always available, but well-behaving components
        # should implement this to inform Home Assistant accordingly.
        return True

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def xy_color(self) -> tuple:
        """Return the XY color value [float, float]."""
        return self._xy_color

    @property
    def rgb_color(self) -> tuple:
        """Return the RBG color value."""
        return self._rgb

    @property
    def color_temp(self) -> int:
        """Return the CT color temperature."""
        return self._ct

    @property
    def white_value(self) -> int:
        """Return the white value of this light between 0..255."""
        return self._white

    @property
    def effect_list(self) -> list:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def effect(self) -> str:
        """Return the current effect."""
        return self._effect

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_DEMO

    def turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        self._state = True

        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]

        if ATTR_COLOR_TEMP in kwargs:
            self._ct = kwargs[ATTR_COLOR_TEMP]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_XY_COLOR in kwargs:
            self._xy_color = kwargs[ATTR_XY_COLOR]

        if ATTR_WHITE_VALUE in kwargs:
            self._white = kwargs[ATTR_WHITE_VALUE]

        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT]

        # As we have disabled polling, we need to inform
        # Home Assistant about updates in our state ourselves.
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._state = False

        # As we have disabled polling, we need to inform
        # Home Assistant about updates in our state ourselves.
        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_restore_state(self, is_on, **kwargs):
        """Restore the demo state."""
        self._state = is_on

        if 'brightness' in kwargs:
            self._brightness = kwargs['brightness']

        if 'color_temp' in kwargs:
            self._ct = kwargs['color_temp']

        if 'rgb_color' in kwargs:
            self._rgb = kwargs['rgb_color']

        if 'xy_color' in kwargs:
            self._xy_color = kwargs['xy_color']

        if 'white_value' in kwargs:
            self._white = kwargs['white_value']

        if 'effect' in kwargs:
            self._effect = kwargs['effect']
