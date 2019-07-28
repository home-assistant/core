"""The Elv integration."""

import logging

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import (
    CONF_NAME, CONF_DEVICE)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_ENERGY_KWH = 'total_energy_kwh'

DOMAIN = 'elv'

NOTIFICATION_ID = 'elv_notification'
NOTIFICATION_TITLE = 'ELV Setup'

ELV_PLATFORMS = ['switch']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_NAME): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the PCA switch platform."""

    # print(config[DOMAIN].get(CONF_DEVICE))
    hass.data[DOMAIN] = {
        'serial_device': config[DOMAIN].get(CONF_DEVICE)
    }
    for platform in ELV_PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True
