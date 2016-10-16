"""
Support for Digital Ocean.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/digital_ocean/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-digitalocean==1.9.0']

_LOGGER = logging.getLogger(__name__)

ATTR_CREATED_AT = 'created_at'
ATTR_DROPLET_ID = 'droplet_id'
ATTR_DROPLET_NAME = 'droplet_name'
ATTR_FEATURES = 'features'
ATTR_IPV4_ADDRESS = 'ipv4_address'
ATTR_IPV6_ADDRESS = 'ipv6_address'
ATTR_MEMORY = 'memory'
ATTR_REGION = 'region'
ATTR_VCPUS = 'vcpus'

CONF_DROPLETS = 'droplets'

DIGITAL_OCEAN = None
DIGITAL_OCEAN_PLATFORMS = ['switch', 'binary_sensor']
DOMAIN = 'digital_ocean'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=unused-argument,too-few-public-methods
def setup(hass, config):
    """Setup the Digital Ocean component."""
    conf = config[DOMAIN]
    access_token = conf.get(CONF_ACCESS_TOKEN)

    global DIGITAL_OCEAN
    DIGITAL_OCEAN = DigitalOcean(access_token)

    if not DIGITAL_OCEAN.manager.get_account():
        _LOGGER.error("No Digital Ocean account found for the given API Token")
        return False

    return True


class DigitalOcean(object):
    """Handle all communication with the Digital Ocean API."""

    def __init__(self, access_token):
        """Initialize the Digital Ocean connection."""
        import digitalocean

        self._access_token = access_token
        self.data = None
        self.manager = digitalocean.Manager(token=self._access_token)

    def get_droplet_id(self, droplet_name):
        """Get the status of a Digital Ocean droplet."""
        droplet_id = None

        all_droplets = self.manager.get_all_droplets()
        for droplet in all_droplets:
            if droplet_name == droplet.name:
                droplet_id = droplet.id

        return droplet_id

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Digital Ocean API."""
        self.data = self.manager.get_all_droplets()
