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


REQUIREMENTS = ['lakeside==0.11']

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
        vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list,
                                                        [DEVICE_SCHEMA]),
        vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
        vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

EUFY_DISPATCH = {
    'T1011': 'light',
    'T1012': 'light',
    'T1013': 'light',
    'T1201': 'switch',
    'T1202': 'switch',
    'T1203': 'switch',
    'T1211': 'switch'
}


def setup(hass, config):
    """Set up Eufy devices."""
    import lakeside

    if CONF_USERNAME in config[DOMAIN] and CONF_PASSWORD in config[DOMAIN]:
        data = lakeside.get_devices(config[DOMAIN][CONF_USERNAME],
                                    config[DOMAIN][CONF_PASSWORD])
        for device in data:
            kind = device['type']
            if kind not in EUFY_DISPATCH:
                continue
            discovery.load_platform(hass, EUFY_DISPATCH[kind], DOMAIN, device,
                                    config)

    for device_info in config[DOMAIN][CONF_DEVICES]:
        kind = device_info['type']
        if kind not in EUFY_DISPATCH:
            continue
        device = {}
        device['address'] = device_info['address']
        device['code'] = device_info['access_token']
        device['type'] = device_info['type']
        device['name'] = device_info['name']
        discovery.load_platform(hass, EUFY_DISPATCH[kind], DOMAIN, device,
                                config)

    return True
