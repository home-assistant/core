"""Support for Tikteck lights."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_PASSWORD
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR,
    Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

SUPPORT_TIKTECK_LED = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tikteck platform."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['password'] = device_config[CONF_PASSWORD]
        device['address'] = address
        light = TikteckLight(device)
        if light.is_valid:
            lights.append(light)

    add_entities(lights)


class TikteckLight(Light):
    """Representation of a Tikteck light."""

    def __init__(self, device):
        """Initialize the light."""
        import tikteck

        self._name = device['name']
        self._address = device['address']
        self._password = device['password']
        self._brightness = 255
        self._hs = [0, 0]
        self._state = False
        self.is_valid = True
        self._bulb = tikteck.tikteck(
            self._address, "Smart Light", self._password)
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error(
                "Failed to connect to bulb %s, %s", self._address, self._name)

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TIKTECK_LED

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def assumed_state(self):
        """Return the assumed state."""
        return True

    def set_state(self, red, green, blue, brightness):
        """Set the bulb state."""
        return self._bulb.set_state(red, green, blue, brightness)

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        self._state = True

        hs_color = kwargs.get(ATTR_HS_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if hs_color is not None:
            self._hs = hs_color
        if brightness is not None:
            self._brightness = brightness

        rgb = color_util.color_hs_to_RGB(*self._hs)

        self.set_state(rgb[0], rgb[1], rgb[2], self.brightness)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self.set_state(0, 0, 0, 0)
        self.schedule_update_ha_state()
