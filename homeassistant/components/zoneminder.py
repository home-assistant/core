"""
Support for ZoneMinder.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zoneminder/
"""
import logging
from urllib.parse import urljoin

import packaging.version
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
    zm_data = {}

    conf = config[DOMAIN]
    if conf[CONF_SSL]:
        schema = 'https'
    else:
        schema = 'http'

    server_origin = '{}://{}'.format(schema, conf[CONF_HOST])
    url = urljoin(server_origin, conf[CONF_PATH])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    zm_data['server_origin'] = server_origin
    zm_data['url'] = url
    zm_data['username'] = username
    zm_data['password'] = password
    zm_data['path_zms'] = conf.get(CONF_PATH_ZMS)
    zm_data['version'] = None

    hass.data[DOMAIN] = zm_data

    return login(hass)


# pylint: disable=no-member
def login(hass):
    """Login to the ZoneMinder API."""
    _LOGGER.debug("Attempting to login to ZoneMinder")

    login_post = {'view': 'console', 'action': 'login'}
    zm_data = hass.data[DOMAIN]
    if zm_data['username']:
        login_post['username'] = zm_data['username']
    if zm_data['password']:
        login_post['password'] = zm_data['password']

    req = requests.post(zm_data['url'] + '/index.php', data=login_post)
    zm_data['cookies'] = req.cookies

    # Login calls returns a 200 response on both failure and success.
    # The only way to tell if you logged in correctly is to issue an api call.
    req = requests.get(
        zm_data['url'] + 'api/host/getVersion.json',
        cookies=zm_data['cookies'],
        timeout=DEFAULT_TIMEOUT)

    if req.ok:
        # Zoneminder always reports the apiversion as 1.0:
        #
        # https://github.com/ZoneMinder/ZoneMinder/blob/8a6105ee5b7aeb241c9336e977b976537235a581/web/api/app/Controller/HostController.php#L117
        #
        # Therefore have to rely on the actual version to determine features.
        zm_data['version'] = None
        version_str = req.json().get('version', None)
        if version_str:
            try:
                zm_data['version'] = packaging.version.parse(version_str)
            except packaging.version.InvalidVersion:
                _LOGGER.exception("Failed to parse version string: %s",
                                  version_str)
    else:
        _LOGGER.error("Connection error logging into ZoneMinder")
        return False

    return True


def _zm_request(hass, method, api_url, data=None):
    """Perform a Zoneminder request."""
    # Since the API uses sessions that expire, sometimes we need to re-auth
    # if the call fails.
    zm_data = hass.data[DOMAIN]
    for _ in range(LOGIN_RETRIES):
        req = requests.request(
            method, urljoin(zm_data['url'], api_url), data=data,
            cookies=zm_data['cookies'], timeout=DEFAULT_TIMEOUT)

        if not req.ok:
            login(hass)
        else:
            break

    else:
        _LOGGER.error("Unable to get API response from ZoneMinder")

    try:
        return req.json()
    except ValueError:
        _LOGGER.exception('JSON decode exception caught while attempting to '
                          'decode "%s"', req.text)


# pylint: disable=no-member
def get_state(hass, api_url):
    """Get a state from the ZoneMinder API service."""
    return _zm_request(hass, 'get', api_url)


# pylint: disable=no-member
def change_state(hass, api_url, post_data):
    """Update a state using the Zoneminder API."""
    return _zm_request(hass, 'post', api_url, data=post_data)


# Introduced in 1.30:
#
# https://github.com/ZoneMinder/ZoneMinder/commit/2888142e682bbc9950535d7e5aaef2cd20cda38d
_ALARM_STATUS_VERSION = packaging.version.parse("1.30")


def alarm_status_supported(hass):
    """Get support for alarm status API."""
    zm_data = hass.data[DOMAIN]
    zm_version = zm_data['version']
    return zm_version is None or zm_version >= _ALARM_STATUS_VERSION
