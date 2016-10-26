"""
Support for TPLink HS100/HS110 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tplink/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/GadgetReactor/pyHS100/archive/'
                '1f771b7d8090a91c6a58931532e42730b021cbde.zip#pyHS100==0.2.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'TPLink Switch HS100'

ATTR_CURRENT_CONSUMPTION = 'Current consumption'
ATTR_TOTAL_CONSUMPTION = 'Total consumption'
ATTR_VOLTAGE = 'Voltage'
ATTR_CURRENT = 'Current'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the TPLink switch platform."""
    from pyHS100.pyHS100 import SmartPlug
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    add_devices([SmartPlugSwitch(SmartPlug(host), name)])


class SmartPlugSwitch(SwitchDevice):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug, name):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._name = name
        self._state = None
        self._emeter_present = (smartplug.model == 110)
        _LOGGER.debug("Setting up TP-Link Smart Plug HS%i", smartplug.model)
        # Set up emeter cache
        self._emeter_params = {}

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state == 'ON'

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.state = 'ON'

    def turn_off(self):
        """Turn the switch off."""
        self.smartplug.state = 'OFF'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._emeter_params

    def update(self):
        """Update the TP-Link switch's state."""
        self._state = self.smartplug.state

        if self._emeter_present:
            emeter_readings = self.smartplug.get_emeter_realtime()

            self._emeter_params[ATTR_CURRENT_CONSUMPTION] \
                = "%.1f W" % emeter_readings["power"]
            self._emeter_params[ATTR_TOTAL_CONSUMPTION] \
                = "%.2f kW" % emeter_readings["total"]
            self._emeter_params[ATTR_VOLTAGE] \
                = "%.2f V" % emeter_readings["voltage"]
            self._emeter_params[ATTR_CURRENT] \
                = "%.1f A" % emeter_readings["current"]
