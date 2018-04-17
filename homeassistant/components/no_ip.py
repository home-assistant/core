"""
Integrate with NO-IP Dynamic DNS service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/no_ip/
"""
import asyncio
import base64
from datetime import timedelta
import logging

import aiohttp
from aiohttp.hdrs import USER_AGENT, AUTHORIZATION
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAIN, CONF_TIMEOUT, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'no_ip'

# We should set a dedicated address for the user agent.
EMAIL = 'hello@home-assistant.io'

INTERVAL = timedelta(minutes=5)

DEFAULT_TIMEOUT = 10

NO_IP_ERRORS = {
    'nohost': "Hostname supplied does not exist under specified account",
    'badauth': "Invalid username password combination",
    'badagent': "Client disabled",
    '!donator':
        "An update request was sent with a feature that is not available",
    'abuse': "Username is blocked due to abuse",
    '911': "A fatal error on NO-IP's side such as a database outage",
}

UPDATE_URL = 'https://dynupdate.noip.com/nic/update'
HA_USER_AGENT = "{} {}".format(SERVER_SOFTWARE, EMAIL)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the NO-IP component."""
    domain = config[DOMAIN].get(CONF_DOMAIN)
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)

    auth_str = base64.b64encode('{}:{}'.format(user, password).encode('utf-8'))

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    result = yield from _update_no_ip(
        hass, session, domain, auth_str, timeout)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_interval(now):
        """Update the NO-IP entry."""
        yield from _update_no_ip(hass, session, domain, auth_str, timeout)

    hass.helpers.event.async_track_time_interval(
        update_domain_interval, INTERVAL)

    return True


@asyncio.coroutine
def _update_no_ip(hass, session, domain, auth_str, timeout):
    """Update NO-IP."""
    url = UPDATE_URL

    params = {
        'hostname': domain,
    }

    headers = {
        AUTHORIZATION: "Basic {}".format(auth_str.decode('utf-8')),
        USER_AGENT: HA_USER_AGENT,
    }

    try:
        with async_timeout.timeout(timeout, loop=hass.loop):
            resp = yield from session.get(url, params=params, headers=headers)
            body = yield from resp.text()

            if body.startswith('good') or body.startswith('nochg'):
                return True

            _LOGGER.warning("Updating NO-IP failed: %s => %s", domain,
                            NO_IP_ERRORS[body.strip()])

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to NO-IP API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from NO-IP API for domain: %s", domain)

    return False
