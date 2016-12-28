"""
Support for Anthem Network Receivers and Processors

"""
import logging
import telnetlib

import voluptuous as vol

DOMAIN = 'anthemav'

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    })

def setup_platform(hass, config, add_devices, discovery_info=None):
    anthemav = AnthemAVR(config.get(CONF_NAME), config.get(CONF_HOST))

    if anthemav.update():
        add_devices([anthemav])
        return True
    else:
        return False

class AnthemAVR(MediaPlayerDevice):
    def __init__(self, name, host):
        """Initialize the Denon device."""
        self._name = name
        self._host = host
