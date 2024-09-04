"""Support for Digital Ocean."""

from datetime import timedelta
import logging

import digitalocean
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_CREATED_AT = "created_at"
ATTR_DROPLET_ID = "droplet_id"
ATTR_DROPLET_NAME = "droplet_name"
ATTR_FEATURES = "features"
ATTR_IPV4_ADDRESS = "ipv4_address"
ATTR_IPV6_ADDRESS = "ipv6_address"
ATTR_MEMORY = "memory"
ATTR_REGION = "region"
ATTR_VCPUS = "vcpus"

ATTRIBUTION = "Data provided by Digital Ocean"

CONF_DROPLETS = "droplets"

DATA_DIGITAL_OCEAN = "data_do"
DIGITAL_OCEAN_PLATFORMS = [Platform.SWITCH, Platform.BINARY_SENSOR]
DOMAIN = "digital_ocean"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Digital Ocean component."""

    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]

    digital = DigitalOcean(access_token)

    try:
        if not digital.manager.get_account():
            _LOGGER.error("No account found for the given API token")
            return False
    except digitalocean.baseapi.DataReadError:
        _LOGGER.error("API token not valid for authentication")
        return False

    hass.data[DATA_DIGITAL_OCEAN] = digital

    return True


class DigitalOcean:
    """Handle all communication with the Digital Ocean API."""

    def __init__(self, access_token):
        """Initialize the Digital Ocean connection."""

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
