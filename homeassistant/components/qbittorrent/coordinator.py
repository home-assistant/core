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
    """Coordinator for updating QBittorrent data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Client) -> None:
        """Initialize coordinator."""
        self.config_entry = entry
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    def update(self) -> SessionStats:
        """Get the latest data from QBittorrent instance."""
        try:
            data = self.client.sync_main_data()
        except LoginRequired as exc:
            raise ConfigEntryError("Invalid authentication") from exc

        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Update QBittorrent data"""
        return await self.hass.async_add_executor_job(self.update)
