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

REQUIREMENTS = ['insteonplm==0.0.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = '/dev/ttyUSB0'
DOMAIN = 'insteon_plm'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up our connection to the PLM."""
    import insteonplm

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)

    _LOGGER.info('Looking for PLM on %s', port)

    def async_insteonplm_update_callback(message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM: %s', message)

    plm = yield from insteonplm.Connection.create(
        device=port, loop=hass.loop,
        update_callback=async_insteonplm_update_callback)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, plm.close)

    return True
