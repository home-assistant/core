"""
Support for Vultr.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/vultr/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['vultr==0.1.2']

_LOGGER = logging.getLogger(__name__)

ATTR_AUTO_BACKUPS = 'auto_backups'
ATTR_ALLOWED_BANDWIDTH_GB = 'allowed_bandwidth_gb'
ATTR_COST_PER_MONTH = 'cost_per_month'
ATTR_CURRENT_BANDWIDTH_GB = 'current_bandwidth_gb'
ATTR_CREATED_AT = 'created_at'
ATTR_DISK = 'disk'
ATTR_SUBSCRIPTION_ID = 'subid'
ATTR_SUBSCRIPTION_NAME = 'label'
ATTR_IPV4_ADDRESS = 'ipv4_address'
ATTR_IPV6_ADDRESS = 'ipv6_address'
ATTR_MEMORY = 'memory'
ATTR_OS = 'os'
ATTR_PENDING_CHARGES = 'pending_charges'
ATTR_REGION = 'region'
ATTR_VCPUS = 'vcpus'

CONF_SUBS = 'subs'

DATA_VULTR = 'data_vultr'
VULTR_PLATFORMS = ['binary_sensor', 'sensor']
DOMAIN = 'vultr'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Vultr component."""
    api_key = config[DOMAIN].get(CONF_API_KEY, None)

    vultr = Vultr(api_key)

    if not vultr.api.account_info():
        _LOGGER.error("No Vultr account found for the given API Key")
        return False

    # Get init data dump
    vultr.update()
    hass.data[DATA_VULTR] = vultr

    return True


class Vultr(object):
    """Handle all communication with the Vultr API."""

    def __init__(self, api_key):
        """Initialize the Vultr connection."""
        from vultr import Vultr as VultrAPI

        self._api_key = api_key
        self.data = {}
        self.api = VultrAPI(self._api_key)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Vultr API."""
        self.data = self.api.server_list()
