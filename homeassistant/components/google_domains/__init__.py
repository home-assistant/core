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

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_DOMAIN): cv.string,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
                    }
                )
            ],        
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize the Google Domains component."""
    domain_configs = config[DOMAIN]

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    result = await _update_all_google_domains(
        hass, session, domain_configs
    )

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the Google Domains entry."""
        await _update_all_google_domains(hass, session, domain_configs)

    hass.helpers.event.async_track_time_interval(update_domain_interval, INTERVAL)

    return True

async def _update_all_google_domains(hass, session, domain_configs):
    """Update a list of Google Domains"""
    final_result = True;

    for domain_config in domain_configs:
        domain = domain_config.get(CONF_DOMAIN)
        user = domain_config.get(CONF_USERNAME)
        password = domain_config.get(CONF_PASSWORD)
        timeout = domain_config.get(CONF_TIMEOUT)

        result = await _update_google_domains(hass, session, domain, user, password, timeout);
        if not result:
            final_result = False;
    
    return final_result;


async def _update_google_domains(hass, session, domain, user, password, timeout):
    """Update Google Domains."""
    url = f"https://{user}:{password}@domains.google.com/nic/update"

    params = {"hostname": domain}

    try:
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
