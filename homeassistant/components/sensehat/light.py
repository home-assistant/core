"""Support for Sense Hat LEDs."""
from sense_hat import SenseHat
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

SUPPORT_SENSEHAT = SUPPORT_BRIGHTNESS | SUPPORT_COLOR

DEFAULT_NAME = "sensehat"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sense Hat Light platform."""

    sensehat = SenseHat()

    name = config.get(CONF_NAME)

    add_entities([SenseHatLight(sensehat, name)])


class SenseHatLight(LightEntity):
    """Representation of an Sense Hat Light."""

    def __init__(self, sensehat, name):
        """Initialize an Sense Hat Light.

        Full brightness and white color.
        """
        self._sensehat = sensehat
        self._name = name
        self._is_on = False
        self._brightness = 255
        self._hs_color = [0, 0]

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Read back the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Read back the color of the light."""
        return self._hs_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SENSEHAT

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
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[ATTR_HS_COLOR]

        rgb = color_util.color_hsv_to_RGB(
            self._hs_color[0], self._hs_color[1], self._brightness / 255 * 100
        )
        self._sensehat.clear(*rgb)

        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._sensehat.clear()
        self._is_on = False
        self.schedule_update_ha_state()
