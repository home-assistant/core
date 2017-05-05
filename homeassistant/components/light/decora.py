"""
Support for Decora dimmers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.decora/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['decora==0.4']

_LOGGER = logging.getLogger(__name__)

SUPPORT_DECORA_LED = (SUPPORT_BRIGHTNESS)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an Decora switch."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['key'] = device_config[CONF_API_KEY]
        device['address'] = address
        light = DecoraLight(device)
        if light.is_valid:
            lights.append(light)

    add_devices(lights)


class DecoraLight(Light):
    """Representation of an Decora light."""

    def __init__(self, device):
        """Initialize the light."""
        # pylint: disable=import-error
        import decora

        self._name = device['name']
        self._address = device['address']
        self._key = device["key"]
        self._switch = decora.decora(self._address, self._key)
        self._switch.connect()
        self._state = self._switch.get_on()
        self._brightness = self._switch.get_brightness()
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
        return SUPPORT_DECORA_LED

    @property
    def should_poll(self):
        """We can read the device state, so poll."""
        return True

    @property
    def assumed_state(self):
        """We can read the actual state."""
        return False

    def set_state(self, brightness):
        """Set the state of this lamp to the provided brightness."""
        self._switch.set_brightness(brightness)
        self._brightness = brightness
        return True

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        self._switch.on()
        if brightness is not None:
            self.set_state(brightness)

        self._state = True

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._switch.off()
        self._state = False

    def update(self):
        """Synchronise internal state with the actual light state."""
        self._brightness = self._switch.get_brightness()
        self._state = self._switch.get_on()
