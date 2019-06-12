"""Support for Juicenet cloud."""
import logging

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'juicenet'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Juicenet component."""
    import pyjuicenet

    hass.data[DOMAIN] = {}

    access_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)
    hass.data[DOMAIN]['api'] = pyjuicenet.Api(access_token)

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
    def _manufacturer_device_id(self):
        """Return the manufacturer device id."""
        return self.device.id()

    @property
    def _token(self):
        """Return the device API token."""
        return self.device.token()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return "{}-{}".format(self.device.id(), self.type)
