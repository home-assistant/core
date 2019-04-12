"""Support for Tibber."""
import asyncio
import logging

import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, CONF_ACCESS_TOKEN,
                                 CONF_NAME)
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['pyTibber==0.10.1']

DOMAIN = 'tibber'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Tibber component."""
    conf = config.get(DOMAIN)

    import tibber
    tibber_connection = tibber.Tibber(conf[CONF_ACCESS_TOKEN],
                                      websession=async_get_clientsession(hass))
    hass.data[DOMAIN] = tibber_connection

    async def _close(event):
        await tibber_connection.rt_disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    try:
        await tibber_connection.update_info()
    except asyncio.TimeoutError as err:
        _LOGGER.error("Timeout connecting to Tibber: %s ", err)
        return False
    except aiohttp.ClientError as err:
        _LOGGER.error("Error connecting to Tibber: %s ", err)
        return False
    except tibber.InvalidLogin as exp:
        _LOGGER.error("Failed to login. %s", exp)
        return False

    for component in ['sensor', 'notify']:
        discovery.load_platform(hass, component, DOMAIN,
                                {CONF_NAME: DOMAIN}, config)

    return True
