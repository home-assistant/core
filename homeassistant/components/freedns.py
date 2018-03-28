"""
Integrate with FreeDNS Dynamic DNS service at freedns.afraid.org.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/freedns/
"""
import asyncio
import base64
from datetime import timedelta
import logging

import aiohttp
from aiohttp.hdrs import USER_AGENT, AUTHORIZATION
import async_timeout
import voluptuous as vol
import yarl

from homeassistant.const import (CONF_URL, CONF_TIMEOUT, CONF_ACCESS_TOKEN)
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'freedns'

# We should set a dedicated address for the user agent.
EMAIL = 'hello@home-assistant.io'

DEFAULT_INTERVAL = timedelta(minutes=10)
DEFAULT_TIMEOUT = 10

UPDATE_URL = 'https://freedns.afraid.org/dynamic/update.php'
HA_USER_AGENT = "{} {}".format(SERVER_SOFTWARE, EMAIL)

CONF_UPDATE_INTERVAL = 'update_interval'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Exclusive(CONF_URL, DOMAIN): cv.string,
        vol.Exclusive(CONF_ACCESS_TOKEN, DOMAIN): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
            cv.time_period, cv.positive_timedelta),

    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the FreeDNS component."""
    url = config[DOMAIN].get(CONF_URL)
    auth_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)
    update_interval = config[DOMAIN].get(CONF_UPDATE_INTERVAL)

    session = hass.helpers.aiohttp_client.async_get_clientsession(False)

    result = yield from _update_freedns(
        hass, session, url, auth_token, timeout)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_callback(now):
        """Update the FreeDNS entry."""
        yield from _update_freedns(hass, session, url, auth_token, timeout)

    hass.helpers.event.async_track_time_interval(
        update_domain_callback, update_interval)

    return True


@asyncio.coroutine
def _update_freedns(hass, session, url, auth_token, timeout):
    """Update FreeDNS."""

    headers = {
        USER_AGENT: HA_USER_AGENT,
    }

    params = None

    if (url == None):
        url = UPDATE_URL

    if not (auth_token == None):
        params = { }
        params[auth_token] = ""

    try:
        with async_timeout.timeout(timeout, loop=hass.loop):
            resp = yield from session.get(url, params=params, headers=headers)
            body = yield from resp.text()

            if "has not changed" in body:
                # IP has not changed.
                return True

            if "ERROR" not in body:
                _LOGGER.debug("Updating FreeDNS was successful: %s", body)
                return True

            if "Invalid update URL" in body:
                _LOGGER.error("FreeDNS update token is invalid")
            else:
                _LOGGER.warning("Updating FreeDNS failed: %s => %s",
                    resp.url, body)

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to FreeDNS API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from FreeDNS API at %s", url)

    return False
