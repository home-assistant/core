"""The Elv integration."""

import logging

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import (
    CONF_NAME, CONF_DEVICE)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'elv'

DEFAULT_DEVICE = '/dev/ttyUSB0'

ELV_PLATFORMS = ['switch']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the PCA switch platform."""

    # hass.data[DOMAIN] = {
    #     'serial_device': config[DOMAIN].get(CONF_DEVICE)
    #     # usb_device = config.get(CONF_DEVICE)
    # }
    print(config)
    for platform in ELV_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True
