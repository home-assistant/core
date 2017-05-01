"""
Support KNX Lighting actuators.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/Light.knx/
"""
import voluptuous as vol

from homeassistant.components.knx import (KNXConfig, KNXGroupAddress)
from homeassistant.components.light import (Light, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'

DEFAULT_NAME = 'KNX Light'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the KNX light platform."""
    add_devices([KNXLight(hass, KNXConfig(config))])


class KNXLight(KNXGroupAddress, Light):
    """Representation of a KNX Light device."""

    def turn_on(self, **kwargs):
        """Turn the switch on.

        This sends a value 1 to the group address of the device
        """
        self.group_write(1)
        self._state = [1]
        if not self.should_poll:
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off.

        This sends a value 1 to the group address of the device
        """
        self.group_write(0)
        self._state = [0]
        if not self.should_poll:
            self.schedule_update_ha_state()
