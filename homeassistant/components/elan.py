"""
Support for elan devices via manual discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/elan/

Setup:
 - Add INELS RF devices in eLAN web interface (follow eLAN manual)
 - Add platfrom url into Home Assistant configuration

Sample configuration:

elan:
  url:  "http://192.168.168.123"

"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv

SERVICE_ELAN = 'elan'

DOMAIN = 'elan'

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
    _LOGGER.info('elan platform setup %s', url)
    offsets = conf.get('offsets')
    _LOGGER.info('elan platform offsets %s', str(offsets))

    @asyncio.coroutine
    def elan_discovered(service, info):
        """Run when a gateway is discovered."""
        url = info['url']
        offsets = info['offsets']
        _LOGGER.info('elan discovered %s', url)
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
