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
    TorrentInfoList,
)
from qbittorrentapi.torrents import TorrentStatusesT

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class QBittorrentDataCoordinator(DataUpdateCoordinator[SyncMainDataDictionary]):
    """Coordinator for updating QBittorrent data."""

    def __init__(self, hass: HomeAssistant, client: Client) -> None:
        """Initialize coordinator."""
        self.client = client
        self._is_alternative_mode_enabled = False
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

    async def _async_update_data(self) -> SyncMainDataDictionary:
        try:
            data = await self.hass.async_add_executor_job(self.client.sync_maindata)
            self._is_alternative_mode_enabled = (
                await self.hass.async_add_executor_job(
                    self.client.transfer_speed_limits_mode
                )
                == "1"
            )
        except (LoginFailed, Forbidden403Error) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="login_error"
            ) from exc
        except APIConnectionError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from exc
        return data

    def set_alt_speed_enabled(self, is_enabled: bool) -> None:
        """Set the alternative speed mode."""
        self.client.transfer_toggle_speed_limits_mode(is_enabled)

    def toggle_alt_speed_enabled(self) -> None:
        """Toggle the alternative speed mode."""
        self.client.transfer_toggle_speed_limits_mode()

    def get_alt_speed_enabled(self) -> bool:
        """Get the alternative speed mode."""
        return self._is_alternative_mode_enabled

    async def get_torrents(self, torrent_filter: TorrentStatusesT) -> TorrentInfoList:
        """Async method to get QBittorrent torrents."""
        try:
            torrents = await self.hass.async_add_executor_job(
                lambda: self.client.torrents_info(torrent_filter)
            )
        except (LoginFailed, Forbidden403Error) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="login_error"
            ) from exc
        except APIConnectionError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from exc

        return torrents
