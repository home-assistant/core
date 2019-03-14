"""Support for EnOcean light sources."""
import logging
import math

import voluptuous as vol

from homeassistant.components import enocean
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import CONF_ID, CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_ID = 'sender_id'

DEFAULT_NAME = 'EnOcean Light'
SUPPORT_ENOCEAN = SUPPORT_BRIGHTNESS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ID, default=[]):
        vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the EnOcean light platform."""
    sender_id = config.get(CONF_SENDER_ID)
    dev_name = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)

    add_entities([EnOceanLight(sender_id, dev_id, dev_name)])


class EnOceanLight(enocean.EnOceanDevice, Light):
    """Representation of an EnOcean light source."""

    def __init__(self, sender_id, dev_id, dev_name):
        """Initialize the EnOcean light source."""
        super().__init__(dev_id, dev_name)
        self._on_state = False
        self._brightness = 50
        self._sender_id = sender_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.dev_name

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

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).
        """
        if packet.data[0] == 0xa5 and packet.data[1] == 0x02:
            val = packet.data[2]
            self._brightness = math.floor(val / 100.0 * 256.0)
            self._on_state = bool(val != 0)
            self.schedule_update_ha_state()
