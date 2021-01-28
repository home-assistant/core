"""Support for Google Domains."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "google_domains"

INTERVAL = timedelta(minutes=5)

DEFAULT_TIMEOUT = 10

IPIFY = "https://api.ipify.org"

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


async def async_setup(hass, config):
    """Initialize the Google Domains component."""
    domain = config[DOMAIN].get(CONF_DOMAIN)
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    address = await _get_ip_address(session, timeout)
    if address is None:
        return False

    result = await _update_google_domains(
        session, domain, user, password, address, timeout
    )
    if not result:
        return False

    async def update_domain_interval(now):
        """Update the Google Domains entry."""
        nonlocal address
        new_address = await _get_ip_address(session, timeout)
        if new_address is not None and new_address != address:
            result = await _update_google_domains(
                hass, session, domain, user, password, timeout, new_address
            )
            if result:
                address = new_address

    hass.helpers.event.async_track_time_interval(update_domain_interval, INTERVAL)

    return True


async def _get_ip_address(session, timeout):
    try:
        with async_timeout.timeout(timeout):
            resp = await session.get(IPIFY)
            return await resp.text()

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to %s", IPIFY)

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from %s", IPIFY)

    return None


async def _update_google_domains(session, domain, user, password, address, timeout):
    try:
        url = f"https://{user}:{password}@domains.google.com/nic/update"
        params = {"hostname": domain, "myip": address}

        with async_timeout.timeout(timeout):
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
