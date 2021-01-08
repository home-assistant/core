"""Support for Blinkt! lights on Raspberry Pi."""
import importlib

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

SUPPORT_BLINKT = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

DEFAULT_NAME = "blinkt"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Blinkt Light platform."""
    # pylint: disable=no-member
    blinkt = importlib.import_module("blinkt")

    # ensure that the lights are off when exiting
    blinkt.set_clear_on_exit()

    name = config[CONF_NAME]

    add_entities(
        [BlinktLight(blinkt, name, index) for index in range(blinkt.NUM_PIXELS)]
    )


class BlinktLight(LightEntity):
    """Representation of a Blinkt! Light."""

    def __init__(self, blinkt, name, index):
        """Initialize a Blinkt Light.

        Default brightness and white color.
        """
        self._blinkt = blinkt
        self._name = f"{name}_{index}"
        self._index = index
        self._is_on = False
        self._brightness = 255
        self._hs_color = [0, 0]

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Read back the brightness of the light.

        Returns integer in the range of 1-255.
        """
        return self._brightness

    @property
    def hs_color(self):
        """Read back the color of the light."""
        return self._hs_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BLINKT

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    @property
    def should_poll(self):
        """Return if we should poll this device."""
        return False

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return True

    def turn_on(self, **kwargs):
        """Instruct the light to turn on and set correct brightness & color."""
        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        percent_bright = self._brightness / 255
        rgb_color = color_util.color_hs_to_RGB(*self._hs_color)
        self._blinkt.set_pixel(
            self._index, rgb_color[0], rgb_color[1], rgb_color[2], percent_bright
        )

        self._blinkt.show()

        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._blinkt.set_pixel(self._index, 0, 0, 0, 0)
        self._blinkt.show()
        self._is_on = False
        self.schedule_update_ha_state()
