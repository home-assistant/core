"""
Support for Mipow lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mipow/
"""
import logging

from homeassistant.components.light import (
    ATTR_RGB_COLOR, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS,
    SUPPORT_RGB_COLOR, Light,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_FLASH, ATTR_FLASH)

REQUIREMENTS = ['mipow==0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mipow'

SUPPORT_MIPOW_LED = (SUPPORT_RGB_COLOR |
                     SUPPORT_FLASH | SUPPORT_BRIGHTNESS)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the mipow platform."""
    name = config.get('name')
    address = config['address']
    light = MipowLight(address, name)
    add_devices_callback([light])


class MipowLight(Light):
    """Representation of a Mipow light."""

    def __init__(self, address, name):
        """Initialize the light."""
        import mipow

        self._name = name
        self._address = address
        self.is_valid = True
        self._bulb = mipow.mipow(self._address)
        self._white = 0
        self._rgb = (0, 0, 0)
        self._state = False
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error(
                "Failed to connect to bulb %s, %s", self._address, self._name)
        self.update()

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._address)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def brightness(self):
        """Return the white property."""
        return self._white

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MIPOW_LED

    @property
    def should_poll(self):
        """Feel free to poll."""
        return True

    @property
    def assumed_state(self):
        """We can report the actual state."""
        return False

    def set_rgb(self, red, green, blue):
        """Set the rgb state."""
        return self._bulb.set_rgb(red, green, blue)

    def set_white(self, white):
        """Set the white state."""
        return self._bulb.set_white(white)

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        self._state = True
        self._bulb.on()

        rgb = kwargs.get(ATTR_RGB_COLOR)
        white = kwargs.get(ATTR_BRIGHTNESS)
        flash = kwargs.get(ATTR_FLASH)
        if flash is not None:
            if flash == FLASH_LONG:
                self.speed = 2
            elif flash == FLASH_SHORT:
                self.speed = 1

        if white is not None:
            self._white = white
            self._rgb = (0, 0, 0)

        if rgb is not None:
            self._white = 0
            self._rgb = rgb

        if self._white != 0 and flash is None:
            self.set_white(self._white)
        elif flash is not None:
            self.set_effect(self._rgb[0], self._rgb[1], self._rgb[2],
                            self._white, 0, self.speed)
        else:
            self.set_rgb(self._rgb[0], self._rgb[1], self._rgb[2])

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self._bulb.off()

    def update(self):
        """Update status."""
        self._rgb = self._bulb.get_colour()
        self._white = self._bulb.get_white()
        self._state = self._bulb.get_on()
