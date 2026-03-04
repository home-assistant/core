"""Coordinator for the WebDAV integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiowebdav2.client import Client
from aiowebdav2.exceptions import UnauthorizedError, WebDavError
from aiowebdav2.models import QuotaInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

type WebDavConfigEntry = ConfigEntry[WebDavRuntimeData]


@dataclass
class WebDavRuntimeData:
    """Runtime data for the WebDAV integration."""

    client: Client
    coordinator: WebDavCoordinator | None = None


class WebDavCoordinator(DataUpdateCoordinator[QuotaInfo]):
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

    async def _async_update_data(self) -> QuotaInfo:
        """Fetch data from WebDAV server."""
        try:
            quota = await self.client.quota()
        except UnauthorizedError as err:
            raise ConfigEntryError("Authentication error") from err
        except WebDavError as err:
            raise UpdateFailed(f"Failed to fetch quota data: {err}") from err

        return quota
