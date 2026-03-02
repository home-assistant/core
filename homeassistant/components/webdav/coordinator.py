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

    quota: QuotaInfo | None


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
        self._supports_quota = True

    async def _async_update_data(self) -> WebDavData:
        """Fetch data from WebDAV server."""
        if not self._supports_quota:
            return WebDavData(quota=None)

        try:
            quota = await self.client.quota()
        except MethodNotSupportedError:
            _LOGGER.debug("WebDAV server does not support quota")
            self._supports_quota = False
            self.update_interval = None
            return WebDavData(quota=None)
        except WebDavError as err:
            raise UpdateFailed(f"Failed to fetch quota data: {err}") from err

        if quota.available_bytes is None and quota.used_bytes is None:
            _LOGGER.debug("WebDAV server does not provide quota information")
            self._supports_quota = False
            self.update_interval = None
            return WebDavData(quota=None)

        return WebDavData(quota=quota)
