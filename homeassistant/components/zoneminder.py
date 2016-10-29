"""
Support for ZoneMinder.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zoneminder/
"""
import logging
import json
from urllib.parse import urljoin

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_PATH, CONF_HOST, CONF_SSL, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_PATH = '/zm/'
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

    url = urljoin('{}://{}'.format(schema, conf[CONF_HOST]), conf[CONF_PATH])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    ZM['url'] = url
    ZM['username'] = username
    ZM['password'] = password

    return login()


# pylint: disable=no-member
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

    if req.status_code != requests.codes.ok:
        _LOGGER.error("Connection error logging into ZoneMinder")
        return False

    return True


# pylint: disable=no-member
def get_state(api_url):
    """Get a state from the ZoneMinder API service."""
    # Since the API uses sessions that expire, sometimes we need to re-auth
    # if the call fails.
    for _ in range(LOGIN_RETRIES):
        req = requests.get(urljoin(ZM['url'], api_url), cookies=ZM['cookies'],
                           timeout=DEFAULT_TIMEOUT)

        if req.status_code != requests.codes.ok:
            login()
        else:
            break
    else:
        _LOGGER.exception("Unable to get API response from ZoneMinder")

    return json.loads(req.text)


# pylint: disable=no-member
def change_state(api_url, post_data):
    """Update a state using the Zoneminder API."""
    for _ in range(LOGIN_RETRIES):
        req = requests.post(
            urljoin(ZM['url'], api_url), data=post_data, cookies=ZM['cookies'],
            timeout=DEFAULT_TIMEOUT)

        if req.status_code != requests.codes.ok:
            login()
        else:
            break

    else:
        _LOGGER.exception("Unable to get API response from ZoneMinder")

    return json.loads(req.text)
