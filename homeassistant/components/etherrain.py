"""
Support for Etherrain/8

"""
import logging
from urllib.parse import urljoin

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_PATH, CONF_HOST, CONF_SSL, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
DOMAIN = 'etherrain'

LOGIN_RETRIES = 2

ER = {}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Etherrain component."""
    global ER
    ER = {}

    conf = config[DOMAIN]
    schema = 'http'

    server_origin = '{}://{}'.format(schema, conf[CONF_HOST])
    username = conf.get(CONF_USERNAME, None)
    password = conf.get(CONF_PASSWORD, None)

    ER['server_origin'] = server_origin
    ER['username'] = username
    ER['password'] = password

    hass.data[DOMAIN] = ER

    return login()


# pylint: disable=no-member
def login():
    """Login to the ZoneMinder API."""
    _LOGGER.info("Attempting to login to ZoneMinder")

    # ergetcfg.cgi?lu=admin\&lp=deadbeef
    url = '{0}/ergetcfg.cgi?lu={1}&lp={2}'.format(ER['server_origin'],ER['username'],ER['password'])
    req = requests.get(url, timeout=DEFAULT_TIMEOUT)

    if not req.ok:
        _LOGGER.error("Connection error logging into EtherRain")
        return False

    return True


def _er_request(method, api_url, data=None):
    """Perform an EtherRain request."""
    for _ in range(LOGIN_RETRIES):
        req = requests.request(
            method, urljoin(ER['url'], api_url), data=data,
            cookies=ER['cookies'], timeout=DEFAULT_TIMEOUT)

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


# pylint: disable=no-member
def get_state(api_url):
    """Get a state from the ZoneMinder API service."""
    return _er_request('get', api_url)


# pylint: disable=no-member
def change_state(api_url, valve_data):
    """Update a state using the Zoneminder API."""
    return _zm_request('get', api_url, data=valve_data)
