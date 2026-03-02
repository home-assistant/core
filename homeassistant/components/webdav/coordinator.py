"""Coordinator for the WebDAV integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiowebdav2.client import Client
from aiowebdav2.exceptions import MethodNotSupportedError, WebDavError
from aiowebdav2.models import QuotaInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

type WebDavConfigEntry = ConfigEntry[WebDavCoordinator]


@dataclass(frozen=True)
class WebDavData:
    """Data class for WebDAV coordinator."""

    quota: QuotaInfo


class WebDavCoordinator(DataUpdateCoordinator[WebDavData]):
    """The WebDAV coordinator."""

    config_entry: WebDavConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
        config_entry: WebDavConfigEntry,
    ) -> None:
        """Initialize the WebDAV coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_setup(self) -> None:
        """Set up the WebDAV coordinator."""
        try:
            quota = await self.client.quota()
        except MethodNotSupportedError:
            _LOGGER.debug("WebDAV server does not support quota")
            await self.async_shutdown()
            return

        if quota.available_bytes is None and quota.used_bytes is None:
            _LOGGER.debug("WebDAV server does not provide quota information")
            await self.async_shutdown()

    async def _async_update_data(self) -> WebDavData:
        """Fetch data from WebDAV server."""
        try:
            quota = await self.client.quota()
        except WebDavError as err:
            raise UpdateFailed(f"Failed to fetch quota data: {err}") from err

        return WebDavData(quota=quota)
