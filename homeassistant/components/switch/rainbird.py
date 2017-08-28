"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""

import logging

import voluptuous as vol

from homeassistant.components import rainbird
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_PLATFORM, CONF_SWITCHES, CONF_ZONE,
                                 CONF_FRIENDLY_NAME, CONF_TRIGGER_TIME,
                                 CONF_SCAN_INTERVAL)
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['rainbird']

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): rainbird.DOMAIN,
    vol.Required(CONF_SWITCHES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_ZONE): cv.string,
            vol.Required(CONF_TRIGGER_TIME): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL): cv.string,
        },
    }),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Rain Bird switches over a Rain Bird controller."""
    devices = []
    rbdevice = hass.data.get("DATA_RAINBIRD")
    for key, switch in config.get(CONF_SWITCHES).items():
        devices.append(RainBirdSwitch(rbdevice, switch))
    add_devices(devices)
    return True


class RainBirdSwitch(SwitchDevice):
    """Representation of a Rain Bird switch."""

    def __init__(self, rb, dev):
        """Initialize a Rain Bird Switch Device."""
        self._rainbird = rb
        self._zone = int(dev.get(CONF_ZONE))
        self._name = dev.get(CONF_FRIENDLY_NAME, "Sprinker %s" % self._zone)
        self._state = self.get_device_status()
        self._duration = dev.get(CONF_TRIGGER_TIME)
        self._attributes = {
            "duration": self._duration,
        }

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self._rainbird.start_irrigation(self._zone, self._duration)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = False
        self._rainbird.stop_irrigation()

    def get_device_status(self):
        """Get the status of the switch from Rain Bird Controller."""
        return self._rainbird.state == self._zone

    def update(self):
        """Update switch status."""
        self._state = self.get_device_status()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
