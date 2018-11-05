"""
Support for Spider Smart devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/spider/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['spiderpy==1.2.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'spider'

SPIDER_COMPONENTS = [
    'climate',
    'switch'
]

SCAN_INTERVAL = timedelta(seconds=120)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Spider Component."""
    from spiderpy.spiderapi import SpiderApi
    from spiderpy.spiderapi import UnauthorizedException

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    refresh_rate = config[DOMAIN][CONF_SCAN_INTERVAL]

    try:
        api = SpiderApi(username, password, refresh_rate.total_seconds())

        hass.data[DOMAIN] = {
            'controller': api,
            'thermostats': api.get_thermostats(),
            'power_plugs': api.get_power_plugs()
        }

        for component in SPIDER_COMPONENTS:
            load_platform(hass, component, DOMAIN, {}, config)

        _LOGGER.debug("Connection with Spider API succeeded")
        return True
    except UnauthorizedException:
        _LOGGER.error("Can't connect to the Spider API")
        return False
