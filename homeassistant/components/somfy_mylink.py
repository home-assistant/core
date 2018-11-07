"""
Platform for the Somfy MyLink device supporting the Synergy JsonRPC API.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/somfy_mylink/
"""
import json
import logging
import socket
from random import randint
from somfy_mylink_synergy import SomfyMyLinkSynergy
import voluptuous as vol
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

_LOGGER = logging.getLogger(__name__)
CONF_COVER_OPTIONS = 'cover_options'
DATA_SOMFY_MYLINK = 'somfy_mylink_data'
DOMAIN = 'somfy_mylink'
SOMFY_MYLINK_COMPONENTS = [
    'cover', 'scene'
]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=44100): cv.port,
        vol.Optional(CONF_COVER_OPTIONS): cv.ensure_list
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Demo covers."""
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    system_id = config[DOMAIN][CONF_PASSWORD]
    try:
        somfy_mylink = SomfyMyLinkSynergy(system_id, host, port)
    except TimeoutError:
        _LOGGER.error("Unable to connect to the Somfy MyLink device, "
                      "please check your settings")
        return False
    hass.data[DATA_SOMFY_MYLINK] = somfy_mylink
    for component in SOMFY_MYLINK_COMPONENTS:
        load_platform(hass, component, DOMAIN, config[DOMAIN])
    return True
