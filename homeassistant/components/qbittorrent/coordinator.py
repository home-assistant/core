"""The QBittorrent coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from qbittorrent import Client
from qbittorrent.client import LoginRequired
from requests import RequestException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class QBittorrentDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """QBittorrent update coordinator."""

    def __init__(self, hass: HomeAssistant, client: Client) -> None:
        """Initialize coordinator."""
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self.client.sync_main_data)
        except RequestException as exc:
            raise UpdateFailed("Connection lost") from exc
        except LoginRequired as exc:
            raise UpdateFailed("Invalid authentication") from exc
