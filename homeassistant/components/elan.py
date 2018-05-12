"""
Support for elan devices manual discovery.
For more details about this component, please refer to the documentation at
https://home-assistant.io/components/elan/
"""

import asyncio
import logging

import async_timeout
import voluptuous as vol

#from homeassistant.components.discovery import SERVICE_elan
SERVICE_ELAN = 'elan'

from homeassistant.helpers import discovery
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from homeassistant.const import EVENT_HOMEASSISTANT_STOP

DOMAIN = 'elan'

#SUBSCRIPTION_REGISTRY = None # do budoucna zde bude ws link k elanu abychom meli upozorneni na zmeny stavu
KNOWN_DEVICES = []

_LOGGER = logging.getLogger(__name__)

CONF_STATIC = 'static'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Required('url'): cv.string,
            vol.Optional('offsets'): {
                cv.string: vol.Coerce(float)
            },
        }),
    },
    extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup elan component."""
    conf = config.get(DOMAIN, {})
    url = conf.get('url')
    _LOGGER.info('elan platform setup ' + url)
    offsets = conf.get('offsets')
    _LOGGER.info('elan platform offsets ' + str(offsets))

    @asyncio.coroutine
    def elan_discovered(service, info):
        """Run when a gateway is discovered."""
        url = info['url']
        offsets = info['offsets']
        _LOGGER.info('elan discovered ' + url)
        yield from _setup_elan(hass, config, url, offsets)

    discovery.async_listen(hass, SERVICE_ELAN, elan_discovered)

    yield from elan_discovered(None, {'url': url, 'offsets': offsets})

    return True


@asyncio.coroutine
def _setup_elan(hass, hass_config, url, offsets):
    """Call platform discovery for devices on particular elan."""
    hass.async_add_job(
        discovery.async_load_platform(hass, 'light', DOMAIN, {'url': url},
                                      hass_config))
    hass.async_add_job(
        discovery.async_load_platform(hass, 'sensor', DOMAIN, {
            'url': url,
            'offsets': offsets
        }, hass_config))
    return True
