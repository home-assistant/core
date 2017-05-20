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


class _Feature:
    def __init__(self, version_str):
        self._version = packaging.version.parse(version_str)

    def is_supported(self):
        """Returns False if this feature isn't supported on the currently
connected zoneminder instance. Otherwise returns True.

        """
        remote_version = ZM.get('version', None)
        if remote_version is None:
            # Be optimistic, assume the remote end supports the feature.
            return True
        return self._version <= remote_version

# Introduced in 1.30:
#
# https://github.com/ZoneMinder/ZoneMinder/commit/2888142e682bbc9950535d7e5aaef2cd20cda38d
ALARM_STATUS_FEATURE = _Feature("1.30")


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
    ZM['version'] = None

    hass.data[DOMAIN] = ZM

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

    if req.ok:
        # Zoneminder always reports the apiversion as 1.0:
        #
        # https://github.com/ZoneMinder/ZoneMinder/blob/8a6105ee5b7aeb241c9336e977b976537235a581/web/api/app/Controller/HostController.php#L117
        #
        # Therefore have to rely on the actual version to determine features.
        ZM['version'] = None
        version_str = req.json().get('version', None)
        if version_str:
            try:
                ZM['version'] = packaging.version.parse(version_str)
            except packaging.version.InvalidVersion:
                _LOGGER.exception("Failed to parse version string: %s", version_str)
    else:
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
        _LOGGER.exception("Unable to get API response from ZoneMinder")

    try:
        return req.json()
    except ValueError:
        _LOGGER.exception('JSON decode exception caught while attempting to '
                          'decode "%s"', req.text)


# pylint: disable=no-member
def get_state(api_url):
    """Get a state from the ZoneMinder API service."""
    return _zm_request('get', api_url)


# pylint: disable=no-member
def change_state(api_url, post_data):
    """Update a state using the Zoneminder API."""
    return _zm_request('post', api_url, data=post_data)
