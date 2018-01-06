"""
Support for MercedesME System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers import discovery

REQUIREMENTS = ['mercedesmejsonpy==0.0.9', 'lxml==4.1.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mercedesme'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=30):
            vol.All(cv.positive_int, vol.Clamp(min=10))
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up MercedesMe System."""
    from mercedesmejsonpy import controller as mbmeAPI

    hass.data[DOMAIN] = {
        'controller': mbmeAPI.Controller(
            config[DOMAIN][CONF_USERNAME],
            config[DOMAIN][CONF_PASSWORD],
            config[DOMAIN][CONF_SCAN_INTERVAL])
    }

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'device_tracker', DOMAIN, {}, config)

    return True
