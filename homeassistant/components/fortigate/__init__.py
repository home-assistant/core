"""Fortigate integration."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, \
    CONF_DEVICES, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'fortigate'

DATA_FGT = DOMAIN

ATTR_NAME = 'name'
DEFAULT_NAME = 'Default State'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Start the fortigate component."""
    conf = config.get(DOMAIN)

    if conf is not None:

        host = conf.get(CONF_HOST)
        user = conf.get(CONF_USERNAME)
        apikey = conf.get(CONF_PASSWORD)
        devices = conf.get(CONF_DEVICES)

        await async_setup_fortigate(hass, config, host, user, apikey, devices)

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_fortigate(hass, config, host, user, apikey, devices):
    """Start up the Fortigate component platforms."""
    from pyFGT.fortigate import FortiGate, FGTConnectionError

    fgt = FortiGate(host, user, apikey=apikey, disable_request_warnings=True)

    try:
        fgt.login()
    except FGTConnectionError:
        _LOGGER.exception('Failed to connect to Fortigate')

    else:
        hass.data[DATA_FGT] = {'fgt': fgt,
                               'devices': devices
                               }

        hass.async_create_task(async_load_platform(
            hass, 'device_tracker', DOMAIN, {}, config))

        async def close_fgt(event):
            """Close Freebox connection on HA Stop."""
            fgt.logout()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_fgt)
