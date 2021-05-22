"""Integrate with DuckDNS."""
from asyncio import iscoroutinefunction
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_TXT = "txt"

DOMAIN = "duckdns"

INTERVAL = timedelta(minutes=5)

SERVICE_SET_TXT = "set_txt"

UPDATE_URL = "https://www.duckdns.org/update"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_TXT_SCHEMA = vol.Schema({vol.Required(ATTR_TXT): vol.Any(None, cv.string)})


async def async_setup(hass, config):
    """Initialize the DuckDNS component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    token = config[DOMAIN][CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    async def update_domain_interval(_now):
        """Update the DuckDNS entry."""
        return await _update_duckdns(session, domain, token)

    intervals = (
        INTERVAL,
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=30),
    )
    async_track_time_interval_backoff(hass, update_domain_interval, intervals)

    async def update_domain_service(call):
        """Update the DuckDNS entry."""
        await _update_duckdns(session, domain, token, txt=call.data[ATTR_TXT])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TXT, update_domain_service, schema=SERVICE_TXT_SCHEMA
    )

    return True


_SENTINEL = object()


async def _update_duckdns(session, domain, token, *, txt=_SENTINEL, clear=False):
    """Update DuckDNS."""
    params = {"domains": domain, "token": token}

    if txt is not _SENTINEL:
        if txt is None:
            # Pass in empty txt value to indicate it's clearing txt record
            params["txt"] = ""
            clear = True
        else:
            params["txt"] = txt

    if clear:
        params["clear"] = "true"

    resp = await session.get(UPDATE_URL, params=params)
    body = await resp.text()

    if body != "OK":
        _LOGGER.warning("Updating DuckDNS domain failed: %s", domain)
        return False

    return True


@callback
@bind_hass
def async_track_time_interval_backoff(hass, action, intervals) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively at every timedelta interval."""
    if not iscoroutinefunction:
        _LOGGER.error("Action needs to be a coroutine and return True/False")
        return

    if not isinstance(intervals, (list, tuple)):
        intervals = (intervals,)
    remove = None
    failed = 0

    async def interval_listener(now):
        """Handle elapsed intervals with backoff."""
        nonlocal failed, remove
        try:
            failed += 1
            if await action(now):
                failed = 0
        finally:
            delay = intervals[failed] if failed < len(intervals) else intervals[-1]
            remove = async_call_later(hass, delay.total_seconds(), interval_listener)

    hass.async_run_job(interval_listener, dt_util.utcnow())

    def remove_listener():
        """Remove interval listener."""
        if remove:
            remove()  # pylint: disable=not-callable

    return remove_listener
