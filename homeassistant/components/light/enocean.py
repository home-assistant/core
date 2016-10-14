"""
Support for EnOcean light sources.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.enocean/
"""
import logging
import math

import voluptuous as vol

from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_ID)
from homeassistant.components import enocean
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_ID = 'sender_id'

DEFAULT_NAME = 'EnOcean Light'

DEPENDENCIES = ['enocean']

SUPPORT_ENOCEAN = SUPPORT_BRIGHTNESS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_SENDER_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the EnOcean light platform."""
    sender_id = config.get(CONF_SENDER_ID)
    devname = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)

    add_devices([EnOceanLight(sender_id, devname, dev_id)])


class EnOceanLight(enocean.EnOceanDevice, Light):
    """Representation of an EnOcean light source."""

    def __init__(self, sender_id, devname, dev_id):
        """Initialize the EnOcean light source."""
        enocean.EnOceanDevice.__init__(self)
        self._on_state = False
        self._brightness = 50
        self._sender_id = sender_id
        self.dev_id = dev_id
        self._devname = devname
        self.stype = 'dimmer'

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._devname

    @property
    def brightness(self):
        """Brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self):
        """If light is on."""
        return self._on_state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ENOCEAN

    def turn_on(self, **kwargs):
        """Turn the light source on or sets a specific dimmer value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        bval = math.floor(self._brightness / 256.0 * 100.0)
        if bval == 0:
            bval = 1
        command = [0xa5, 0x02, bval, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn the light source off."""
        command = [0xa5, 0x02, 0x00, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = False

    def value_changed(self, val):
        """Update the internal state of this device."""
        self._brightness = math.floor(val / 100.0 * 256.0)
        self._on_state = bool(val != 0)
        self.update_ha_state()
