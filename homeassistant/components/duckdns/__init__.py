"""Integrate with DuckDNS with support for updating IPv4 and IPv6."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime, timedelta
import logging
from typing import Any, cast

from aiohttp import ClientSession
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import (
    CALLBACK_TYPE,
    HassJob,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_TXT = "txt"

DOMAIN = "duckdns"

INTERVAL = timedelta(minutes=5)

SERVICE_SET_TXT = "set_txt"

UPDATE_URL = "https://www.duckdns.org/update"

CONF_IPV4_FETCH_URL = "ipv4_fetch_url"
CONF_IPV6_FETCH_URL = "ipv6_fetch_url"
CONF_IP_UPDATE_MODE = "ip_update_mode"

# Define the configuration schema with ip_update_mode only on configuration level
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(
                    CONF_IPV4_FETCH_URL, default="https://api.ipify.org"
                ): cv.url,
                vol.Optional(
                    CONF_IPV6_FETCH_URL, default="https://api6.ipify.org"
                ): cv.url,
                vol.Optional(CONF_IP_UPDATE_MODE, default="ipv4"): vol.In(
                    ["ipv4", "ipv6", "both"]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Service schema for setting TXT record without ip_update_mode
SERVICE_TXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TXT): vol.Any(None, cv.string),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the DuckDNS component."""
    domain: str = config[DOMAIN][CONF_DOMAIN]
    token: str = config[DOMAIN][CONF_ACCESS_TOKEN]
    ipv4_fetch_url: str = config[DOMAIN][CONF_IPV4_FETCH_URL]
    ipv6_fetch_url: str = config[DOMAIN][CONF_IPV6_FETCH_URL]
    ip_update_mode: str = config[DOMAIN][CONF_IP_UPDATE_MODE]
    session = async_get_clientsession(hass)

    async def update_domain_interval(_now: datetime) -> bool:
        """Update the DuckDNS entry with configured IP update mode."""
        return await _update_duckdns(
            session,
            domain,
            token,
            ipv4_fetch_url=ipv4_fetch_url,
            ipv6_fetch_url=ipv6_fetch_url,
            ip_update_mode=ip_update_mode,
        )

    # Define retry intervals
    intervals = (
        INTERVAL,
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=30),
    )
    async_track_time_interval_backoff(hass, update_domain_interval, intervals)

    async def update_domain_service(call: ServiceCall) -> None:
        """Update the DuckDNS entry based on service call data."""
        await _update_duckdns(
            session,
            domain,
            token,
            txt=call.data[ATTR_TXT],
            ipv4_fetch_url=ipv4_fetch_url,
            ipv6_fetch_url=ipv6_fetch_url,
            ip_update_mode=ip_update_mode,
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TXT, update_domain_service, schema=SERVICE_TXT_SCHEMA
    )

    return True


_SENTINEL = object()


async def _fetch_ipv6(session: ClientSession, ipv6_fetch_url: str) -> str | None:
    """Fetch the current IPv6 address using a configurable URL."""
    try:
        async with session.get(ipv6_fetch_url) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        _LOGGER.warning("Failed to fetch IPv6 address: %s", e)
    return None


async def _fetch_ipv4(session: ClientSession, ipv4_fetch_url: str) -> str | None:
    """Fetch the current IPv4 address using a configurable URL."""
    try:
        async with session.get(ipv4_fetch_url) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        _LOGGER.warning("Failed to fetch IPv4 address: %s", e)
    return None


async def _update_duckdns(
    session: ClientSession,
    domain: str,
    token: str,
    *,
    txt: str | None | object = _SENTINEL,
    ip_update_mode: str = "ipv4",
    ipv4_fetch_url: str,
    ipv6_fetch_url: str,
    clear: bool = False,
) -> bool:
    """Update DuckDNS entry with the specified IP versions."""
    params = {"domains": domain, "token": token}

    # Handle TXT record updates
    if txt is not _SENTINEL:
        if txt is None:
            params["txt"] = ""
            clear = True
        else:
            params["txt"] = cast(str, txt)

    if clear:
        params["clear"] = "true"

    # When ip_update_mode is ipv4 only, duckdns detects ip automatically
    if ip_update_mode == "both":
        ipv4_address = await _fetch_ipv4(session, ipv4_fetch_url)
        if ipv4_address:
            params["ip"] = ipv4_address.strip()

    if ip_update_mode in ["ipv6", "both"]:
        ipv6_address = await _fetch_ipv6(session, ipv6_fetch_url)
        if ipv6_address:
            params["ipv6"] = ipv6_address.strip()

    # Send update request to DuckDNS
    resp = await session.get(UPDATE_URL, params=params)
    body = await resp.text()

    if body != "OK":
        _LOGGER.warning("Updating DuckDNS domain failed: %s", domain)
        return False

    return True


@callback
@bind_hass
def async_track_time_interval_backoff(
    hass: HomeAssistant,
    action: Callable[[datetime], Coroutine[Any, Any, bool]],
    intervals: Sequence[timedelta],
) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively at every timedelta interval."""
    remove: CALLBACK_TYPE | None = None
    failed = 0

    async def interval_listener(now: datetime) -> None:
        """Handle elapsed intervals with backoff."""
        nonlocal failed, remove
        try:
            failed += 1
            if await action(now):
                failed = 0
        finally:
            delay = intervals[failed] if failed < len(intervals) else intervals[-1]
            remove = async_call_later(
                hass, delay.total_seconds(), interval_listener_job
            )

    interval_listener_job = HassJob(interval_listener, cancel_on_shutdown=True)
    hass.async_run_hass_job(interval_listener_job, dt_util.utcnow())

    def remove_listener() -> None:
        """Remove interval listener."""
        if remove:
            remove()

    return remove_listener
