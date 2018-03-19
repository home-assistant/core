"""
Support for Eufy devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/eufy/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS, \
    CONF_DEVICES, CONF_USERNAME, CONF_PASSWORD, CONF_TYPE, CONF_NAME
from homeassistant.helpers import discovery

import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['lakeside==0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'eufy'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_TYPE): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

EUFY_DISPATCH = {
    'T1011': 'light',
    'T1012': 'light',
    'T1013': 'light',
    'T1201': 'switch',
    'T1202': 'switch',
    'T1211': 'switch'
}

def setup(hass, config):
    """Set up Eufy devices."""
    # pylint: disable=import-error
    import lakeside

    if CONF_USERNAME in config[DOMAIN] and CONF_PASSWORD in config[DOMAIN]:
        data = lakeside.get_devices(config[DOMAIN][CONF_USERNAME],
                                    config[DOMAIN][CONF_PASSWORD])
        for device in data:
            type = device['type']
            if type not in EUFY_DISPATCH:
                continue
            discovery.load_platform(hass, EUFY_DISPATCH[type], DOMAIN, device,
                                    config)

    for address, access_token, type, name in \
        config[DOMAIN][CONF_DEVICES].items():
        if type not in EUFY_DISPATCH:
            continue
        device = {}
        device['address'] = address
        device['code'] = access_token
        device['type'] = type
        device['name'] = name
        discovery.load_platform(hass, EUFY_DISPATCH[type], DOMAIN, device,
                                config)

    return True
