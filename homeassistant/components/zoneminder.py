"""
Support for ZoneMinder.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zoneminder/
"""
import logging
from urllib.parse import urljoin

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_PATH, CONF_HOST, CONF_SSL, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_PATH_ZMS = 'path_zms'
DEFAULT_PATH = '/zm/'
DEFAULT_PATH_ZMS = '/zm/cgi-bin/nph-zms'
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DOMAIN = 'zoneminder'

LOGIN_RETRIES = 2

ZM = {}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
        # This should match PATH_ZMS in ZoneMinder settings.
        vol.Optional(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the ZoneMinder component."""
    global ZM
    ZM = {}

    conf = config[DOMAIN]
    if conf[CONF_SSL]:
        schema = 'https'
    else:
        schema = 'http'

    server_origin = '{}://{}'.format(schema, conf[CONF_HOST])
    url = urljoin(server_origin, conf[CONF_PATH])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    ZM['server_origin'] = server_origin
    ZM['url'] = url
    ZM['username'] = username
    ZM['password'] = password
    ZM['path_zms'] = conf.get(CONF_PATH_ZMS)

    hass.data[DOMAIN] = ZM

    return login()


def login():
    """Login to the ZoneMinder API."""
    _LOGGER.debug("Attempting to login to ZoneMinder")

    login_post = {'view': 'console', 'action': 'login'}
    if ZM['username']:
        login_post['username'] = ZM['username']
    if ZM['password']:
        login_post['password'] = ZM['password']

    req = requests.post(ZM['url'] + '/index.php', data=login_post)
    ZM['cookies'] = req.cookies

    # Login calls returns a 200 response on both failure and success.
    # The only way to tell if you logged in correctly is to issue an api call.
    req = requests.get(
        ZM['url'] + 'api/host/getVersion.json', cookies=ZM['cookies'],
        timeout=DEFAULT_TIMEOUT)

    if not req.ok:
        _LOGGER.error("Connection error logging into ZoneMinder")
        return False

    return True


def _zm_request(method, api_url, data=None):
    """Perform a Zoneminder request."""
    # Since the API uses sessions that expire, sometimes we need to re-auth
    # if the call fails.
    for _ in range(LOGIN_RETRIES):
        req = requests.request(
            method, urljoin(ZM['url'], api_url), data=data,
            cookies=ZM['cookies'], timeout=DEFAULT_TIMEOUT)

        if not req.ok:
            login()
        else:
            break

    else:
        _LOGGER.error("Unable to get API response from ZoneMinder")

    try:
        return req.json()
    except ValueError:
        _LOGGER.exception('JSON decode exception caught while attempting to '
                          'decode "%s"', req.text)


def get_state(api_url):
    """Get a state from the ZoneMinder API service."""
    return _zm_request('get', api_url)


def change_state(api_url, post_data):
    """Update a state using the Zoneminder API."""
    return _zm_request('post', api_url, data=post_data)
