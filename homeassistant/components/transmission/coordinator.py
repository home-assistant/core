"""Coordinator for transmssion integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import transmission_rpc
from transmission_rpc.session import SessionStats

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DEFAULT_LIMIT,
    DEFAULT_ORDER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_DOWNLOADED_TORRENT,
    EVENT_REMOVED_TORRENT,
    EVENT_STARTED_TORRENT,
)

_LOGGER = logging.getLogger(__name__)


class TransmissionDataUpdateCoordinator(DataUpdateCoordinator[SessionStats]):
    """Transmission dataupdate coordinator class."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: transmission_rpc.Client
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.config_entry = entry
        self.api = api
        self.host = entry.data[CONF_HOST]
        self._session: transmission_rpc.Session | None = None
        self._all_torrents: list[transmission_rpc.Torrent] = []
        self._completed_torrents: list[transmission_rpc.Torrent] = []
        self._started_torrents: list[transmission_rpc.Torrent] = []
        self.torrents: list[transmission_rpc.Torrent] = []
        super().__init__(
            hass,
            name=f"{DOMAIN} - {self.host}",
            logger=_LOGGER,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def limit(self) -> int:
        """Return limit."""
        return self.config_entry.options.get(CONF_LIMIT, DEFAULT_LIMIT)

    @property
    def order(self) -> str:
        """Return order."""
        return self.config_entry.options.get(CONF_ORDER, DEFAULT_ORDER)

    async def _async_update_data(self) -> SessionStats:
        """Update transmission data."""
        return await self.hass.async_add_executor_job(self.update)

    def update(self) -> SessionStats:
        """Get the latest data from Transmission instance."""
        try:
            data = self.api.session_stats()
            self.torrents = self.api.get_torrents()
            self._session = self.api.get_session()
        except transmission_rpc.TransmissionError as err:
            raise UpdateFailed("Unable to connect to Transmission client") from err

        self.check_completed_torrent()
        self.check_started_torrent()
        self.check_removed_torrent()

        return data

    def init_torrent_list(self) -> None:
        """Initialize torrent lists."""
        self.torrents = self.api.get_torrents()
        self._completed_torrents = [
            torrent for torrent in self.torrents if torrent.status == "seeding"
        ]
        self._started_torrents = [
            torrent for torrent in self.torrents if torrent.status == "downloading"
        ]

    def check_completed_torrent(self) -> None:
        """Get completed torrent functionality."""
        old_completed_torrents = {torrent.id for torrent in self._completed_torrents}

        current_completed_torrents = [
            torrent for torrent in self.torrents if torrent.status == "seeding"
        ]

        for torrent in current_completed_torrents:
            if torrent.id not in old_completed_torrents:
                self.hass.bus.fire(
                    EVENT_DOWNLOADED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._completed_torrents = current_completed_torrents

    def check_started_torrent(self) -> None:
        """Get started torrent functionality."""
        old_started_torrents = {torrent.id for torrent in self._started_torrents}

        current_started_torrents = [
            torrent for torrent in self.torrents if torrent.status == "downloading"
        ]

        for torrent in current_started_torrents:
            if torrent.id not in old_started_torrents:
                self.hass.bus.fire(
                    EVENT_STARTED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._started_torrents = current_started_torrents

    def check_removed_torrent(self) -> None:
        """Get removed torrent functionality."""
        current_torrents = {torrent.id for torrent in self.torrents}

        for torrent in self._all_torrents:
            if torrent.id not in current_torrents:
                self.hass.bus.fire(
                    EVENT_REMOVED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._all_torrents = self.torrents.copy()

    def start_torrents(self) -> None:
        """Start all torrents."""
        if not self.torrents:
            return
        self.api.start_all()

    def stop_torrents(self) -> None:
        """Stop all active torrents."""
        if not self.torrents:
            return
        torrent_ids: list[int | str] = [torrent.id for torrent in self.torrents]
        self.api.stop_torrent(torrent_ids)

    def set_alt_speed_enabled(self, is_enabled: bool) -> None:
        """Set the alternative speed flag."""
        self.api.set_session(alt_speed_enabled=is_enabled)

    def get_alt_speed_enabled(self) -> bool | None:
        """Get the alternative speed flag."""
        if self._session is None:
            return None

        return self._session.alt_speed_enabled
