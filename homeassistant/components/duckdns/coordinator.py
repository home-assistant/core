"""Coordinator for the Duck DNS integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

from aiohttp import ClientError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type DuckDnsConfigEntry = ConfigEntry[DuckDnsUpdateCoordinator]

INTERVAL = timedelta(minutes=5)
BACKOFF_INTERVALS = (
    INTERVAL,
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
)

UPDATE_URL = "https://www.duckdns.org/update"
_SENTINEL = object()


class DuckDnsUpdateCoordinator(DataUpdateCoordinator[bool]):
    """Duck DNS update coordinator."""

    config_entry: DuckDnsConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: DuckDnsConfigEntry) -> None:
        """Initialize the Duck DNS update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=INTERVAL,
        )
        self.session = async_get_clientsession(hass)
        self.failed = 0

    async def _async_update_data(self) -> bool:
        """Update Duck DNS."""

        retry_after = BACKOFF_INTERVALS[
            min(self.failed, len(BACKOFF_INTERVALS))
        ].total_seconds()

        try:
            if not await _update_duckdns(
                self.session,
                self.config_entry.data[CONF_DOMAIN],
                self.config_entry.data[CONF_ACCESS_TOKEN],
            ):
                self.failed += 1
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                    translation_placeholders={
                        CONF_DOMAIN: self.config_entry.data[CONF_DOMAIN],
                    },
                    retry_after=retry_after,
                )
        except ClientError as e:
            self.failed += 1
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={
                    CONF_DOMAIN: self.config_entry.data[CONF_DOMAIN],
                },
                retry_after=retry_after,
            ) from e
        self.failed = 0

        return True


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
