"""Integrate with NO-IP Dynamic DNS service."""
import asyncio
import base64
from datetime import datetime, timedelta
import logging

import aiohttp
from aiohttp.hdrs import AUTHORIZATION, USER_AGENT
import async_timeout
import voluptuous as vol
from collections import OrderedDict

from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "no_ip"

# We should set a dedicated address for the user agent.
EMAIL = "hello@home-assistant.io"

INTERVAL = timedelta(minutes=1)

DEFAULT_TIMEOUT = 10

NO_IP_ERRORS = {
    "nohost": "Hostname supplied does not exist under specified account",
    "badauth": "Invalid username password combination",
    "badagent": "Client disabled",
    "!donator": "An update request was sent with a feature that is not available",
    "abuse": "Username is blocked due to abuse",
    "911": "A fatal error on NO-IP's side such as a database outage",
}

UPDATE_URL = "https://dynupdate.no-ip.com/nic/update"
HA_USER_AGENT = f"{SERVER_SOFTWARE} {EMAIL}"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: [
            vol.Schema(
                {
                    vol.Required(CONF_DOMAIN): cv.string,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
                }
            )
        ]
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    """Run throght all domains"""
    _LOGGER.debug("Start no ip custom client %s" % config)
    for ordered_dict_items in config[DOMAIN]:
        state_call= await _caller_no_ip(hass, ordered_dict_items)
        
    return True

async def _caller_no_ip(
        hass: HomeAssistant,
        item: ConfigType) -> bool:

    """Initialize the NO-IP component. For a single domain"""
    domain = item.get(CONF_DOMAIN)
    user = item.get(CONF_USERNAME)
    password = item.get(CONF_PASSWORD)
    timeout = item.get(CONF_TIMEOUT)

    auth_str = base64.b64encode(f"{user}:{password}".encode())

    session = async_get_clientsession(hass)

    async def update_domain_interval(now: datetime) -> None:
        """Update the NO-IP entry."""
        _LOGGER.debug("Update for DOMAIN: %s " % (domain))
        result = await _update_no_ip(hass, session, domain, auth_str, timeout)
    
    _LOGGER.debug("Prepare listner for DOMAIN: %s " % (domain))
    async_track_time_interval(hass, update_domain_interval, INTERVAL)

    return True


async def _update_no_ip(
    hass: HomeAssistant,
    session: aiohttp.ClientSession,
    domain: str,
    auth_str: bytes,
    timeout: int,
) -> bool:
    """Update NO-IP."""
    url = UPDATE_URL

    params = {"hostname": domain}

    headers = {
        AUTHORIZATION: f"Basic {auth_str.decode('utf-8')}",
        USER_AGENT: HA_USER_AGENT,
    }
    
    _LOGGER.debug("_update_no_ip for DOMAIN: %s " % (domain))

    try:
        async with async_timeout.timeout(timeout):
            resp = await session.get(url, params=params, headers=headers)
            body = await resp.text()

            if body.startswith("good") or body.startswith("nochg"):
                _LOGGER.debug("Updating NO-IP success: %s", domain)
                return True

            _LOGGER.warning(
                "Updating NO-IP failed: %s => %s", domain, NO_IP_ERRORS[body.strip()]
            )

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to NO-IP API [%s]", domain)

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from NO-IP API for domain: %s", domain)

    return False
