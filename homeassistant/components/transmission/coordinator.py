"""Coordinator for transmission integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import logging

import transmission_rpc
from transmission_rpc.session import SessionStats

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DOWNLOAD_PATH,
    ATTR_LABELS,
    CONF_LIMIT,
    CONF_ORDER,
    DEFAULT_LIMIT,
    DEFAULT_ORDER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_DOWNLOADED_TORRENT,
    EVENT_REMOVED_TORRENT,
    EVENT_STARTED_TORRENT,
    EVENT_TYPE_DOWNLOADED,
    EVENT_TYPE_REMOVED,
    EVENT_TYPE_STARTED,
)

_LOGGER = logging.getLogger(__name__)

type EventCallback = Callable[[TransmissionEventData], None]
type TransmissionConfigEntry = ConfigEntry[TransmissionDataUpdateCoordinator]


@dataclass
class TransmissionEventData:
    """Data for a single event."""

    event_type: str
    name: str
    id: int
    download_path: str
    labels: list[str]


class TransmissionDataUpdateCoordinator(DataUpdateCoordinator[SessionStats]):
    """Transmission dataupdate coordinator class."""

    config_entry: TransmissionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TransmissionConfigEntry,
        api: transmission_rpc.Client,
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.api = api
        self.host = entry.data[CONF_HOST]
        self._session: transmission_rpc.Session | None = None
        self._all_torrents: list[transmission_rpc.Torrent] = []
        self._completed_torrents: list[transmission_rpc.Torrent] = []
        self._started_torrents: list[transmission_rpc.Torrent] = []
        self._event_listeners: dict[str, EventCallback] = {}
        self.torrents: list[transmission_rpc.Torrent] = []
        super().__init__(
            hass,
            config_entry=entry,
            name=f"{DOMAIN} - {self.host}",
            logger=_LOGGER,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def limit(self) -> int:
        """Return limit."""
        return self.config_entry.options.get(CONF_LIMIT, DEFAULT_LIMIT)  # type: ignore[no-any-return]

    @property
    def order(self) -> str:
        """Return order."""
        return self.config_entry.options.get(CONF_ORDER, DEFAULT_ORDER)  # type: ignore[no-any-return]

    @callback
    def async_add_event_listener(
        self, update_callback: EventCallback, target_event_id: str
    ) -> Callable[[], None]:
        """Listen for updates."""
        self._event_listeners[target_event_id] = update_callback
        return partial(self.__async_remove_listener_internal, target_event_id)

    def __async_remove_listener_internal(self, listener_id: str) -> None:
        self._event_listeners.pop(listener_id, None)

    @callback
    def _async_notify_event_listeners(self, event: TransmissionEventData) -> None:
        """Notify event listeners in the event loop."""
        for listener in list(self._event_listeners.values()):
            listener(event)

    async def _async_update_data(self) -> SessionStats:
        """Update transmission data."""
        data = await self.hass.async_add_executor_job(self.update)

        self.check_completed_torrent()
        self.check_started_torrent()
        self.check_removed_torrent()

        return data

    def update(self) -> SessionStats:
        """Get the latest data from Transmission instance."""
        try:
            data = self.api.session_stats()
            self.torrents = self.api.get_torrents()
            self._session = self.api.get_session()
        except transmission_rpc.TransmissionError as err:
            raise UpdateFailed("Unable to connect to Transmission client") from err

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
                # Once event triggers are out of labs we can remove the bus event
                self.hass.bus.async_fire(
                    EVENT_DOWNLOADED_TORRENT,
                    {
                        ATTR_NAME: torrent.name,
                        ATTR_ID: torrent.id,
                        ATTR_DOWNLOAD_PATH: torrent.download_dir,
                        ATTR_LABELS: torrent.labels,
                    },
                )
                event = TransmissionEventData(
                    event_type=EVENT_TYPE_DOWNLOADED,
                    name=torrent.name,
                    id=torrent.id,
                    download_path=torrent.download_dir or "",
                    labels=torrent.labels,
                )
                self._async_notify_event_listeners(event)

        self._completed_torrents = current_completed_torrents

    def check_started_torrent(self) -> None:
        """Get started torrent functionality."""
        old_started_torrents = {torrent.id for torrent in self._started_torrents}

        current_started_torrents = [
            torrent for torrent in self.torrents if torrent.status == "downloading"
        ]

        for torrent in current_started_torrents:
            if torrent.id not in old_started_torrents:
                # Once event triggers are out of labs we can remove the bus event
                self.hass.bus.async_fire(
                    EVENT_STARTED_TORRENT,
                    {
                        ATTR_NAME: torrent.name,
                        ATTR_ID: torrent.id,
                        ATTR_DOWNLOAD_PATH: torrent.download_dir,
                        ATTR_LABELS: torrent.labels,
                    },
                )
                event = TransmissionEventData(
                    event_type=EVENT_TYPE_STARTED,
                    name=torrent.name,
                    id=torrent.id,
                    download_path=torrent.download_dir or "",
                    labels=torrent.labels,
                )
                self._async_notify_event_listeners(event)

        self._started_torrents = current_started_torrents

    def check_removed_torrent(self) -> None:
        """Get removed torrent functionality."""
        current_torrents = {torrent.id for torrent in self.torrents}

        for torrent in self._all_torrents:
            if torrent.id not in current_torrents:
                # Once event triggers are out of labs we can remove the bus event
                self.hass.bus.async_fire(
                    EVENT_REMOVED_TORRENT,
                    {
                        ATTR_NAME: torrent.name,
                        ATTR_ID: torrent.id,
                        ATTR_DOWNLOAD_PATH: torrent.download_dir,
                        ATTR_LABELS: torrent.labels,
                    },
                )
                event = TransmissionEventData(
                    event_type=EVENT_TYPE_REMOVED,
                    name=torrent.name,
                    id=torrent.id,
                    download_path=torrent.download_dir or "",
                    labels=torrent.labels,
                )
                self._async_notify_event_listeners(event)

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
