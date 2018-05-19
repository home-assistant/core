"""
Support for getting daily kwh usage information from Florida Power & Light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fpl/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

REQUIREMENTS = ['python-fpl-api==0.0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'fpl'
DATA_FPL = 'fpl_data'
SCAN_INTERVAL = timedelta(hours=6)

CONF_IS_TOU_USER = 'is_tou'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_IS_TOU_USER, default=False): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the FPL component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    is_tou = conf.get(CONF_IS_TOU_USER)

    session = async_get_clientsession(hass)
    hass.data[DATA_FPL] = FplData(
        username, password, is_tou, hass.loop, session)
    load_platform(
        hass, 'sensor', DOMAIN,
        {
            'yesterday_kwh': True, 'yesterday_dollars': True,
            'mtd_kwh': True, 'mtd_dollars': True
        }, config
    )
    return True


class FplData(object):
    """Get the latest data from the FPL API."""

    def __init__(self, username, password, is_tou, loop, session):
        """Init the 3rd party library."""
        from pyfplapi import FplApi
        self.client = FplApi(username, password, is_tou, loop, session)

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the latest data from the FPL API."""
        _LOGGER.debug("Updating FPL component")
        await self.client.login()
        await asyncio.wait([self.client.async_get_yesterday_usage(),
                            self.client.async_get_mtd_usage()])
