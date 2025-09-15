"""Integrate with DuckDNS."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime, timedelta
import logging
from typing import Any, cast

from aiohttp import ClientSession
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import (
    CALLBACK_TYPE,
    HassJob,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_TXT = "txt"

DOMAIN = "duckdns"

INTERVAL = timedelta(minutes=5)
BACKOFF_INTERVALS = (
    INTERVAL,
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
)
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

type DuckDnsConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the DuckDNS component."""

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DuckDnsConfigEntry) -> bool:
    """Set up Duck DNS from a config entry."""
    domain = entry.data[CONF_DOMAIN]
    token = entry.data[CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    async def update_domain_interval(_now: datetime) -> bool:
        """Update the DuckDNS entry."""
        return await _update_duckdns(session, domain, token)

    entry.async_on_unload(
        async_track_time_interval_backoff(
            hass, update_domain_interval, BACKOFF_INTERVALS
        )
    )

    async def update_domain_service(call: ServiceCall) -> None:
        """Update the DuckDNS entry."""
        await _update_duckdns(session, domain, token, txt=call.data[ATTR_TXT])

    hass.services.async_register(
        DOMAIN, SERVICE_SET_TXT, update_domain_service, schema=SERVICE_TXT_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DuckDnsConfigEntry) -> bool:
    """Unload a config entry."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_TXT)
    return True


_SENTINEL = object()


async def _update_duckdns(
    session: ClientSession,
    domain: str,
    token: str,
    *,
    txt: str | None | object = _SENTINEL,
    clear: bool = False,
) -> bool:
    """Update DuckDNS."""
    params = {"domains": domain, "token": token}

    if txt is not _SENTINEL:
        if txt is None:
            # Pass in empty txt value to indicate it's clearing txt record
            params["txt"] = ""
            clear = True
        else:
            params["txt"] = cast(str, txt)

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
