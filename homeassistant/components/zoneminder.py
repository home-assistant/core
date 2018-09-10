"""
Support for ZoneMinder.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zoneminder/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PATH, CONF_SSL, CONF_USERNAME,
    CONF_VERIFY_SSL)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_PATH_ZMS = 'path_zms'

DEFAULT_PATH = '/zm/'
DEFAULT_PATH_ZMS = '/zm/cgi-bin/nph-zms'
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DEFAULT_VERIFY_SSL = True
DOMAIN = 'zoneminder'

LOGIN_RETRIES = 2

ZM = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the ZoneMinder component."""
    from zoneminder.zm import ZoneMinder
    global ZM
    ZM = None

    conf = config[DOMAIN]
    if conf[CONF_SSL]:
        schema = 'https'
    else:
        schema = 'http'

    server_origin = '{}://{}'.format(schema, conf[CONF_HOST])
    ZM = ZoneMinder(server_origin, conf.get(CONF_USERNAME, None), conf.get(CONF_PASSWORD, None),
                    conf.get(CONF_PATH), conf.get(CONF_PATH_ZMS), conf.get(CONF_VERIFY_SSL))

    hass.data[DOMAIN] = ZM

    return login()


def login():
    """Login to the ZoneMinder API."""
    global ZM
    return ZM.login()


def get_state(api_url):
    """Get a state from the ZoneMinder API service."""
    global ZM
    return ZM._zm_request('get', api_url)


def change_state(api_url, post_data):
    """Update a state using the Zoneminder API."""
    global ZM
    return ZM._zm_request('post', api_url, data=post_data)
