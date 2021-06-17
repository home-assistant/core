"""Integrate with Gandi Live DNS service."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
from aiohttp.hdrs import AUTHORIZATION
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_TTL,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "gandi_livedns"

INTERVAL = timedelta(minutes=5)

CONF_IPV6 = "ipv6"

DEFAULT_TIMEOUT = 10
DEFAULT_TTL = 3600
DEFAULT_TYPE = "A"
DEFAULT_IPV6 = False

AVAILABLE_TYPE = [
    "A",
    "AAAA",
    "ALIAS",
    "CAA",
    "CDS",
    "CNAME",
    "DNAME",
    "DS",
    "KEY",
    "LOC",
    "MX",
    "NAPTR",
    "NS",
    "OPENPGPKEY",
    "PTR",
    "RP",
    "SPF",
    "SRV",
    "SSHFP",
    "TLSA",
    "TXT",
    "WKS",
]

IPV4_PROVIDER_URL = "https://api.ipify.org"
IPV6_PROVIDER_URL = "https://api6.ipify.org"

GANDI_LIVEDNS_API_URL = (
    "https://api.gandi.net/v5/livedns/domains/{domain}/records/{rrname}/{rrtype}"
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_NAME): cv.string,
                vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.In(AVAILABLE_TYPE),
                vol.Optional(CONF_TTL, default=DEFAULT_TTL): cv.positive_int,
                vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize the component."""
    domain = config[DOMAIN].get(CONF_DOMAIN)
    apikey = config[DOMAIN].get(CONF_API_KEY)
    rrname = config[DOMAIN].get(CONF_NAME)
    rrtype = config[DOMAIN].get(CONF_TYPE)
    rrttl = config[DOMAIN].get(CONF_TTL)
    ipv6 = config[DOMAIN].get(CONF_IPV6)
    timeout = config[DOMAIN].get(CONF_TIMEOUT)

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    apikey = f"{apikey}".encode("utf-8")

    """Update the rrvalues entry."""
    result = await _update_gandi_livedns(
        session, domain, rrname, rrtype, rrttl, apikey, timeout, ipv6
    )

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the rrvalues entry."""
        await _update_gandi_livedns(
            session, domain, rrname, rrtype, rrttl, apikey, timeout, ipv6
        )

    hass.helpers.event.async_track_time_interval(update_domain_interval, INTERVAL)

    return True


async def _get_real_ip(session, timeout, ipv6):

    url = IPV4_PROVIDER_URL

    if ipv6:
        url = IPV6_PROVIDER_URL

    try:
        with async_timeout.timeout(timeout):
            resp = await session.get(url)
            body = await resp.text()
            _LOGGER.debug("Real IP: %s - %s", resp.status, body)
            if resp.status == 200:
                return body
            else:
                return False

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect for getting real ip")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from real ip getting")

    return False


async def _get_gandi_livedns(
    session, domain, rrname, rrtype, rrttl, apikey, timeout, ipv6
):

    url_params = {
        "domain": domain,
        "rrname": rrname,
        "rrtype": rrtype,
    }

    url = GANDI_LIVEDNS_API_URL.format(**url_params)

    _LOGGER.debug("Request url: %s", url)

    headers = {AUTHORIZATION: f"Apikey {apikey.decode('utf-8')}"}

    try:
        with async_timeout.timeout(timeout):
            resp = await session.get(url, headers=headers)
            body = await resp.json()

            if resp.status == 200:
                return body["rrset_values"][0]

            _LOGGER.warning("Getting %s failed: (%s) %s", url, resp.status, body)

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from API for: %s", url)

    return False


async def _update_gandi_livedns(
    session, domain, rrname, rrtype, rrttl, apikey, timeout, ipv6
):
    """Update the rrset_values and rrset_ttl entry in Gandi."""

    current_ip = await _get_real_ip(session, timeout, ipv6)
    if not current_ip:
        _LOGGER.warning("Can't get the real ip")
        return False

    current_gandi_ip = await _get_gandi_livedns(
        session, domain, rrname, rrtype, rrttl, apikey, timeout, ipv6
    )
    if not current_gandi_ip:
        _LOGGER.warning("Can't get the current dns ip")
        return False

    if current_gandi_ip == current_ip:
        _LOGGER.debug("No need update dns")
        return True

    url_params = {
        "domain": domain,
        "rrname": rrname,
        "rrtype": rrtype,
    }

    url = GANDI_LIVEDNS_API_URL.format(**url_params)

    json = {"rrset_ttl": rrttl, "rrset_values": [current_ip]}

    headers = {AUTHORIZATION: f"Apikey {apikey.decode('utf-8')}"}

    try:
        with async_timeout.timeout(timeout):
            resp = await session.put(url, json=json, headers=headers)
            body = await resp.text()

            if resp.status == 201:
                _LOGGER.info(
                    "Gandi live dns updated with ttl: %s ip: %s", rrttl, current_ip
                )
                return True

            _LOGGER.warning("Updating %s failed: (%s) %s", url, resp.status, body)

    except aiohttp.ClientError:
        _LOGGER.warning("Can't connect to API")

    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from API for: %s", domain)

    return False
