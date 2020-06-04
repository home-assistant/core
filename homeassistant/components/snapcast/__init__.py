"""The snapcast component."""
import logging
import socket


import voluptuous as vol

import snapcast.control
from snapcast.control.server import CONTROL_PORT

from homeassistant.helpers.discovery import async_load_platform

from homeassistant.helpers import config_validation as cv, entity_platform

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)

from .const import (
    ATTR_LATENCY,
    ATTR_MASTER,
    CLIENT_PREFIX,
    CLIENT_SUFFIX,
    DATA_KEY,
    GROUP_PREFIX,
    GROUP_SUFFIX,
    SERVICE_JOIN,
    SERVICE_RESTORE,
    SERVICE_SET_LATENCY,
    SERVICE_SNAPSHOT,
    SERVICE_UNJOIN,
    GROUP_DISABLE,
)

_LOGGER = logging.getLogger(__name__)

# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
#   {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_PORT): cv.port}
# )

CONFIG_SCHEMA = vol.Schema(
    {
        DATA_KEY: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT): cv.port,
                vol.Optional(GROUP_DISABLE): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """setup of platform"""
    conf = config.get(DATA_KEY)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT, CONTROL_PORT)

    try:
        server = await snapcast.control.create_server(
            hass.loop, host, port, reconnect=True
        )

    except socket.gaierror:
        _LOGGER.error("Could not connect to Snapcast server at %s:%d", host, port)
        return

    # Note: Host part is needed, when using multiple snapservers
    hpid = f"{host}:{port}"

    hass.data[DATA_KEY] = {
        "server": server,
        "hpid": hpid,
        GROUP_DISABLE: conf.get(GROUP_DISABLE, False),
    }

    hass.async_create_task(
        async_load_platform(hass, "media_player", DATA_KEY, {}, config)
    )

    hass.async_create_task(async_load_platform(hass, "sensor", DATA_KEY, {}, config))

    return True
