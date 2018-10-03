"""
Integrate with FreeDNS Dynamic DNS service at freedns.afraid.org.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/freedns/
"""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (CONF_URL, CONF_ACCESS_TOKEN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'freedns'

DEFAULT_INTERVAL = timedelta(minutes=10)

TIMEOUT = 10
UPDATE_URL = 'https://freedns.afraid.org/dynamic/update.php'

CONF_UPDATE_INTERVAL = 'update_interval'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Exclusive(CONF_URL, DOMAIN): cv.string,
        vol.Exclusive(CONF_ACCESS_TOKEN, DOMAIN): cv.string,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
            cv.time_period, cv.positive_timedelta),

    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the FreeDNS component."""
    url = config[DOMAIN].get(CONF_URL)
    auth_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)
    update_interval = config[DOMAIN].get(CONF_UPDATE_INTERVAL)

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    result = await _update_freedns(
        hass, session, url, auth_token)

    if result is False:
        return False

    async def update_domain_callback(now):
        """Update the FreeDNS entry."""
        await _update_freedns(hass, session, url, auth_token)

    hass.helpers.event.async_track_time_interval(
        update_domain_callback, update_interval)

    return True


async def _update_freedns(hass, session, url, auth_token):
    """Update FreeDNS."""
    params = None

    if url is None:
        url = UPDATE_URL

    if auth_token is not None:
        params = {}
        params[auth_token] = ""

    try:
        with async_timeout.timeout(TIMEOUT, loop=hass.loop):
            resp = await session.get(url, params=params)
            body = await resp.text()

            if "has not changed" in body:
                # IP has not changed.
                _LOGGER.debug("FreeDNS update skipped: IP has not changed")
                return True

            if "ERROR" not in body:
                _LOGGER.debug("Updating FreeDNS was successful: %s", body)
                return True

            if "Invalid update URL" in body:
                _LOGGER.error("FreeDNS update token is invalid")
            else:
                _LOGGER.warning("Updating FreeDNS failed: %s", body)

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to FreeDNS API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from FreeDNS API at %s", url)

    return False
