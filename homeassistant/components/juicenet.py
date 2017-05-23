"""
Support for Juicenet cloud.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/juicenet
"""

import logging

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-juicenet==0.0.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'juicenet'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCESS_TOKEN): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Juicenet component."""
    import pyjuicenet

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]['unique_ids'] = []
    hass.data[DOMAIN]['entities'] = {}

    access_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)

    hass.data[DOMAIN]['api'] = pyjuicenet.Api(access_token)

    hass.data[DOMAIN]['entities']['sensor'] = []
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)

    return True


class JuicenetDevice(Entity):
    """Represent a base Juicenet device."""

    def __init__(self, device, sensor_type, hass):
        """Initialise the sensor."""
        self.hass = hass
        self.device = device
        self.type = sensor_type

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name()

    def update(self):
        """Update state of the device."""
        self.device.update_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        if self.type == 'status':
            man_dev_id = self._manufacturer_device_id
            if man_dev_id:
                attributes["manufacturer_device_id"] = man_dev_id
        return attributes

    @property
    def _manufacturer_device_id(self):
        """Return the manufacturer device id."""
        return self.device.id()

    @property
    def _token(self):
        """Return the device API token."""
        return self.device.token()

    @property
    def unique_id(self):
        """Return an unique ID."""
        return "{}-{}".format(self.device.id(), self.type)
