"""
Enable ptvsd debugger to attach to HA.

Attach ptvsd debugger by default to port 5678.
"""

import logging
from threading import Thread
from asyncio import Event

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

DOMAIN = 'ptvsd'

CONF_WAIT = 'wait'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(
            CONF_HOST, default='0.0.0.0'
        ): cv.string,
        vol.Optional(
            CONF_PORT, default=5678
        ): cv.port,
        vol.Optional(
            CONF_WAIT, default=False
        ): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up ptvsd debugger."""
    import ptvsd

    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]

    ptvsd.enable_attach((host, port))

    wait = conf[CONF_WAIT]
    if wait:
        _LOGGER.warning("Waiting for ptvsd connection on %s:%s", host, port)
        ready = Event()

        def waitfor():
            ptvsd.wait_for_attach()
            hass.loop.call_soon_threadsafe(ready.set)
        Thread(target=waitfor).start()

        await ready.wait()
    else:
        _LOGGER.warning("Listening for ptvsd connection on %s:%s", host, port)

    return True
