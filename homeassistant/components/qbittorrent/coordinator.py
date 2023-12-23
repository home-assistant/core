"""The QBittorrent coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from qbittorrent import Client
from qbittorrent.client import LoginRequired

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class QBittorrentDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for updating qBittorrent data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Client) -> None:
        """Initialize coordinator."""
        self.config_entry = entry
        self.client = client
        # self.main_data: dict[str, int] = {}
        self.total_torrents: dict[str, int] = {}
        self.active_torrents: dict[str, int] = {}
        self.inactive_torrents: dict[str, int] = {}
        self.paused_torrents: dict[str, int] = {}
        self.seeding_torrents: dict[str, int] = {}
        self.started_torrents: dict[str, int] = {}


        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    def update(self) -> SessionStats:
        """Get the latest data from qBittorrent instance."""
        try:
            data = self.client.sync_main_data()
            self.total_torrents = self.client.torrents(filter='all')
            self.active_torrents = self.client.torrents(filter='active')
            self.inactive_torrents = self.client.torrents(filter='inactive')
            self.paused_torrents = self.client.torrents(filter='paused')
            self.seeding_torrents = self.client.torrents(filter='seeding')
            self.started_torrents = self.client.torrents(filter='started')
        except LoginRequired as exc:
            raise ConfigEntryError("Invalid authentication") from exc

        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Update qBittorrent data"""
        return await self.hass.async_add_executor_job(self.update)
