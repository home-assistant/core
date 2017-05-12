"""
Support for Avion dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.avion/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['avion==0.6']

_LOGGER = logging.getLogger(__name__)

SUPPORT_AVION_LED = (SUPPORT_BRIGHTNESS)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an Avion switch."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['key'] = device_config[CONF_API_KEY]
        device['address'] = address
        light = AvionLight(device)
        if light.is_valid:
            lights.append(light)

    add_devices(lights)


class AvionLight(Light):
    """Representation of an Avion light."""

    def __init__(self, device):
        """Initialize the light."""
        # pylint: disable=import-error
        import avion

        self._name = device['name']
        self._address = device['address']
        self._key = device['key']
        self._brightness = 255
        self._state = False
        self._switch = avion.avion(self._address, self._key)
        self._switch.connect()
        self.is_valid = True

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
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_AVION_LED

    @property
    def should_poll(self):
        """Don't poll."""
        return False

    @property
    def assumed_state(self):
        """We can't read the actual state, so assume it matches."""
        return True

    def set_state(self, brightness):
        """Set the state of this lamp to the provided brightness."""
        self._switch.set_brightness(brightness)
        return True

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None:
            self._brightness = brightness

        self.set_state(self.brightness)
        self._state = True

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self.set_state(0)
        self._state = False
