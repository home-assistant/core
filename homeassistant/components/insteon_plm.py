"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['insteonplm==0.7.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = '/dev/ttyUSB0'
DOMAIN = 'insteon_plm'

CONF_DEBUG = 'debug'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

PLM_PLATFORMS = [
    'binary_sensor', 'light', 'switch'
]


@asyncio.coroutine
def async_setup(hass, config):
    """Set up our connection to the PLM."""
    import insteonplm

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)

    _LOGGER.info('Looking for PLM on %s', port)

    plm = yield from insteonplm.Connection.create(
        device=port, loop=hass.loop)

    hass.data['insteon_plm'] = plm

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, plm.close)

    for platform in PLM_PLATFORMS:
        _LOGGER.info('Trying to load platform %s', platform)
        hass.async_add_job(discovery.async_load_platform(hass, platform, DOMAIN, config))

    return True

def common_attributes(entity):
    """Return the device state attributes."""
    attributes = {}
    attributekeys = {}
    attributekeys['address'] = 'INSTEON Address'
    attributekeys['description'] = 'Description'
    attributekeys['model'] = 'Model'
    attributekeys['cat'] = 'Category'
    attributekeys['subcat'] = 'Subcategory'
    attributekeys['firmware'] = 'Firmware'
    attributekeys['product_key'] = 'Product Key'

    hexkeys = ['cat', 'subcat', 'firmware']

    for key in attributekeys:
        name = attributekeys[key]
        val = entity._plm.device_attribute(entity._address, key)
        if val is not None:
            if key in hexkeys:
                attributes[name] = hex(int(val))
            else:
                attributes[name] = val
    return attributes
