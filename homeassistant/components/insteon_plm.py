"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['insteonplm==0.7.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_OVERRIDE, default=[]): cv.ensure_list_csv,
    })
}, extra=vol.ALLOW_EXTRA)

PLM_PLATFORMS = {
    'binary_sensor': ['binary_sensor'],
    'light': ['light'],
    'switch': ['switch'],
}


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the connection to the PLM."""
    import insteonplm

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    overrides = conf.get(CONF_OVERRIDE)

    @callback
    def async_plm_new_device(device):
        """Detect device from transport to be delegated to platform."""
        name = device.get('address')
        address = device.get('address_hex')
        capabilities = device.get('capabilities', [])

        _LOGGER.info("New INSTEON PLM device: %s (%s) %r",
                     name, address, capabilities)

        loadlist = []
        for platform in PLM_PLATFORMS:
            caplist = PLM_PLATFORMS.get(platform)
            for key in capabilities:
                if key in caplist:
                    loadlist.append(platform)

        loadlist = sorted(set(loadlist))

        for loadplatform in loadlist:
            hass.async_add_job(
                discovery.async_load_platform(
                    hass, loadplatform, DOMAIN, discovered=[device],
                    hass_config=config))

    _LOGGER.info("Looking for PLM on %s", port)
    plm = yield from insteonplm.Connection.create(device=port, loop=hass.loop)

    for device in overrides:
        #
        # Override the device default capabilities for a specific address
        #
        if isinstance(device['platform'], list):
            plm.protocol.devices.add_override(
                device['address'], 'capabilities', device['platform'])
        else:
            plm.protocol.devices.add_override(
                device['address'], 'capabilities', [device['platform']])

    hass.data['insteon_plm'] = plm

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, plm.close)

    plm.protocol.devices.add_device_callback(async_plm_new_device, {})

    return True


def common_attributes(entity):
    """Return the device state attributes."""
    attributes = {}
    attributekeys = {
        'address': 'INSTEON Address',
        'description': 'Description',
        'model': 'Model',
        'cat': 'Category',
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
