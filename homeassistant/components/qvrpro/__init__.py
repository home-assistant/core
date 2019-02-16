"""Support for QVR Pro NVR software by QNAP"""

import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_USERNAME, \
    CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from .const import DOMAIN

REQUIREMENTS = ['pyqvrpro==0.43']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the QVR Pro component"""
    from pyqvrpro import Client
    from pyqvrpro.client import AuthenticationError

    user = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]

    try:
        qvrpro = Client(user, password, host)
    except AuthenticationError:
        _LOGGER.error(
            'QVR Pro authentication failed.  Please check your credentials.')
        return False

    channel_resp = qvrpro.get_channel_list()

    channels = []

    for channel in channel_resp['channels']:
        channels.append(QVRChannel(**channel))

    hass.data[DOMAIN] = {
        'channels': channels,
        'client': qvrpro
    }

    load_platform(hass, 'camera', DOMAIN, {}, config)

    return True


class QVRChannel:
    """Representation of a QVR channel"""

    def __init__(self, name, model, brand, channel_index, guid):
        self.name = name
        self._model = model
        self.brand = brand
        self._index = channel_index
        self.guid = guid
