"""Coordinator for the Duck DNS integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .helpers import update_duckdns

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


class DuckDnsUpdateCoordinator(DataUpdateCoordinator[None]):
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

    async def _async_update_data(self) -> None:
        """Update Duck DNS."""

        retry_after = BACKOFF_INTERVALS[
            min(self.failed, len(BACKOFF_INTERVALS))
        ].total_seconds()

        try:
            if not await update_duckdns(
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
