"""
Support for AVM Fritz!Box fritzhome devices.

For more details about this component, please refer to the documentation at
http://home-assistant.io/components/fritzhome/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyfritzhome==0.3.5']

SUPPORTED_DOMAINS = ['climate', 'switch']

DOMAIN = 'fritzhome'

DEFAULT_HOST = 'fritz.box'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the fritzhome component."""
    from pyfritzhome import Fritzhome, LoginError

    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    try:
        fritz = Fritzhome(host=host, user=username, password=password)
        fritz.login()
        hass.data[DOMAIN] = fritz.get_devices()
    except LoginError:
        _LOGGER.warning("Login to Fritz!Box failed")
        return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, fritz.logout)

    for domain in SUPPORTED_DOMAINS:
        discovery.load_platform(hass, domain, DOMAIN, {}, config)

    _LOGGER.info('Connected to fritzbox')

    return True
