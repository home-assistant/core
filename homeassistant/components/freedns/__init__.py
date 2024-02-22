"""Integrate with FreeDNS Dynamic DNS service at freedns.afraid.org."""
import asyncio
from datetime import datetime, timedelta
import logging

import aiohttp
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "freedns"

DEFAULT_INTERVAL = timedelta(minutes=10)

TIMEOUT = 10
UPDATE_URL = "https://freedns.afraid.org/dynamic/update.php"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Exclusive(CONF_URL, DOMAIN): cv.string,
                vol.Exclusive(CONF_ACCESS_TOKEN, DOMAIN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
                    cv.time_period, cv.positive_timedelta
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the FreeDNS component."""
    conf = config[DOMAIN]
    url = conf.get(CONF_URL)
    auth_token = conf.get(CONF_ACCESS_TOKEN)
    update_interval = conf[CONF_SCAN_INTERVAL]

    session = async_get_clientsession(hass)

    result = await _update_freedns(hass, session, url, auth_token)

    if result is False:
        return False

    async def update_domain_callback(now: datetime) -> None:
        """Update the FreeDNS entry."""
        await _update_freedns(hass, session, url, auth_token)

    async_track_time_interval(
        hass, update_domain_callback, update_interval, cancel_on_shutdown=True
    )

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
        async with asyncio.timeout(TIMEOUT):
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

    except TimeoutError:
        _LOGGER.warning("Timeout from FreeDNS API at %s", url)

    return False
