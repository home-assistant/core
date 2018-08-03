"""
Support for Edimax switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.edimax/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyedimax==0.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Edimax Smart Plug'
DEFAULT_PASSWORD = '1234'
DEFAULT_USERNAME = 'admin'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Edimax Smart Plugs."""
    from pyedimax.smartplug import SmartPlug

    host = config.get(CONF_HOST)
    auth = (config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    name = config.get(CONF_NAME)

    add_devices([SmartPlugSwitch(SmartPlug(host, auth), name)])


class SmartPlugSwitch(SwitchDevice):
    """Representation an Edimax Smart Plug switch."""

    def __init__(self, smartplug, name):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._name = name
        self._now_power = None
        self._now_energy_day = None
        self._state = False

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._now_power

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return self._now_energy_day

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.state = 'ON'

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.smartplug.state = 'OFF'

    def update(self):
        """Update edimax switch."""
        try:
            self._now_power = float(self.smartplug.now_power)
        except (TypeError, ValueError):
            self._now_power = None

        try:
            self._now_energy_day = float(self.smartplug.now_energy_day)
        except (TypeError, ValueError):
            self._now_energy_day = None

        self._state = self.smartplug.state == 'ON'
