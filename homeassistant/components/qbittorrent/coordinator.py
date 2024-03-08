"""The QBittorrent coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from qbittorrentapi import (
    APIConnectionError,
    Client,
    Forbidden403Error,
    LoginFailed,
    SyncMainDataDictionary,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class QBittorrentDataCoordinator(DataUpdateCoordinator[SyncMainDataDictionary]):
    """Coordinator for updating QBittorrent data."""

    def __init__(self, hass: HomeAssistant, client: Client) -> None:
        """Initialize coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> SyncMainDataDictionary:
        try:
            return await self.hass.async_add_executor_job(self.client.sync_maindata)
        except (LoginFailed, Forbidden403Error) as exc:
            raise ConfigEntryError("Invalid authentication") from exc
        except APIConnectionError as exc:
            raise ConfigEntryError("Fail to connect to qBittorrentApi") from exc
