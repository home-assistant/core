"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['insteonplm==0.7.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_OVERRIDE, default=[]): vol.All(
            cv.ensure_list_csv, vol.Length(min=1))
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
    overrides = conf.get(CONF_OVERRIDE)

    _LOGGER.info('Looking for PLM on %s', port)

    plm = yield from insteonplm.Connection.create(
        device=port, loop=hass.loop)

    for device in overrides:
        #
        # Override the device default capabilities for a specific address
        #
        plm.protocol.devices.add_override(
            device['address'], 'capabilities', [device['platform']])

    hass.data['insteon_plm'] = plm

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, plm.close)

    for platform in PLM_PLATFORMS:
        _LOGGER.info('Trying to load platform %s', platform)
        hass.async_add_job(
            discovery.async_load_platform(hass, platform, DOMAIN, config))

    return True


def common_attributes(entity):
    """Return the device state attributes."""
    attributes = {}
    attributekeys = {
        'address': 'INSTEON Address',
        'description': 'Description',
        'model': 'Model',
        'cat': 'Cagegory',
        'subcat': 'Subcategory',
        'firmware': 'Firmware',
        'product_key': 'Product Key'
    }

    hexkeys = ['cat', 'subcat', 'firmware']

    for key in attributekeys:
        name = attributekeys[key]
        val = entity.get_attr(key)
        if val is not None:
            if key in hexkeys:
                attributes[name] = hex(int(val))
            else:
                attributes[name] = val
    return attributes
