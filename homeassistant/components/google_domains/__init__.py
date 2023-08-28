"""Support for Google Domains."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "google_domains"

INTERVAL = timedelta(minutes=5)

DEFAULT_TIMEOUT = 10

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the Google Domains component."""
    domain = config[DOMAIN].get(CONF_DOMAIN)
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)

    session = async_get_clientsession(hass)

    result = await _update_google_domains(
        hass, session, domain, user, password, timeout
    )

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the Google Domains entry."""
        await _update_google_domains(hass, session, domain, user, password, timeout)

    async_track_time_interval(hass, update_domain_interval, INTERVAL)

    return True


async def _update_google_domains(hass, session, domain, user, password, timeout):
    """Update Google Domains."""
    url = f"https://{user}:{password}@domains.google.com/nic/update"

    params = {"hostname": domain}

    try:
        async with asyncio.timeout(timeout):
            resp = await session.get(url, params=params)
            body = await resp.text()

            if body.startswith("good") or body.startswith("nochg"):
                return True

            _LOGGER.warning("Updating Google Domains failed: %s => %s", domain, body)

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to Google Domains API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from Google Domains API for domain: %s", domain)

    return False
