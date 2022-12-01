"""The Dynamic DNS for OVH integration."""
import asyncio
import base64
from datetime import datetime, timedelta
import logging

import aiohttp
from aiohttp.hdrs import AUTHORIZATION
import async_timeout
import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ddns_ovh"

INTERVAL = timedelta(minutes=1)

DEFAULT_TIMEOUT = 10

UPDATE_URL = "https://www.ovh.com/nic/update"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required("triggered_by_event", default=False): cv.boolean,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Dynamic DNS for OVH from a config entry."""
    domain = config[DOMAIN].get(CONF_DOMAIN)
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)
    triggered_by_event = config[DOMAIN].get("triggered_by_event")

    auth_str = base64.b64encode(f"{user}:{password}".encode())

    session = async_get_clientsession(hass)

    if triggered_by_event:
        return await _event_handling(hass, session, domain, auth_str, timeout)

    return await _pull(hass, session, domain, auth_str, timeout)


async def _event_handling(
    hass: HomeAssistant,
    session: aiohttp.ClientSession,
    domain: str,
    auth_str: bytes,
    timeout: int,
) -> bool:
    async def handle_event(event: Event):
        _LOGGER.debug("Ip Address: %s", event.data["ip"])
        external_ip: str = event.data["ip"]
        if external_ip != "":
            await _update_ip(hass, session, domain, auth_str, timeout, external_ip)

    hass.bus.async_listen("external_ip_provided_event", handle_event)
    return True


async def _pull(
    hass: HomeAssistant,
    session: aiohttp.ClientSession,
    domain: str,
    auth_str: bytes,
    timeout: int,
) -> bool:
    result = await _update_ip(hass, session, domain, auth_str, timeout, external_ip="")

    if not result:
        return False

    async def update_domain_interval(now: datetime) -> None:
        """Update the OVH entry."""
        await _update_ip(hass, session, domain, auth_str, timeout, external_ip="")

    async_track_time_interval(hass, update_domain_interval, INTERVAL)

    return True


async def _update_ip(
    hass: HomeAssistant,
    session: aiohttp.ClientSession,
    domain: str,
    auth_str: bytes,
    timeout: int,
    external_ip: str,
) -> bool:
    """Update OVH."""
    url = UPDATE_URL

    if external_ip != "":
        params = {"hostname": domain, "system": "dyndns", "myip": external_ip}
    else:
        params = {"hostname": domain, "system": "dyndns"}

    headers = {AUTHORIZATION: f"Basic {auth_str.decode('utf-8')}"}

    try:
        async with async_timeout.timeout(timeout):
            resp = await session.get(url, params=params, headers=headers)
            body = await resp.text()

            if body.startswith("good") or body.startswith("nochg"):
                return True

            _LOGGER.warning("Updating OVH failed: %s => %s", domain, body.strip())

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to OVH API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from OVH API for domain: %s", domain)

    return False
