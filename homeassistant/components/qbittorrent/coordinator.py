"""The QBittorrent coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from qbittorrent import Client
from qbittorrent.client import LoginRequired

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class QBittorrentDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for updating QBittorrent data."""

    def __init__(
        self, hass: HomeAssistant, client: Client, is_alternative_mode_enabled: bool
    ) -> None:
        """Initialize coordinator."""
        self.client = client
        self._is_alternative_mode_enabled = is_alternative_mode_enabled

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.hass.async_add_executor_job(self.client.sync_main_data)
            self._is_alternative_mode_enabled = await self.hass.async_add_executor_job(
                self.client.get_alternative_speed_status
            )
        except LoginRequired as exc:
            raise ConfigEntryError("Invalid authentication") from exc
        return data

    def set_alt_speed_enabled(self, is_enabled: bool) -> None:
        """Set the alternative speed mode."""
        if self.get_alt_speed_enabled() != is_enabled:
            self.toggle_alt_speed_enabled()

    def toggle_alt_speed_enabled(self) -> None:
        """Toggle the alternative speed mode."""
        self.client.toggle_alternative_speed()

    def get_alt_speed_enabled(self) -> bool:
        """Get the alternative speed mode."""
        return self._is_alternative_mode_enabled
