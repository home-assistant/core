"""Coordinator for transmssion integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import transmission_rpc
from transmission_rpc.session import SessionStats
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
    CONF_ENTRY_ID,
    CONF_LIMIT,
    CONF_ORDER,
    DEFAULT_DELETE_DATA,
    DEFAULT_LIMIT,
    DEFAULT_ORDER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_DOWNLOADED_TORRENT,
    EVENT_REMOVED_TORRENT,
    EVENT_STARTED_TORRENT,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_ENTRY_ID, "identifier"): selector.ConfigEntrySelector(),
    }
)

SERVICE_ADD_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend({vol.Required(ATTR_TORRENT): cv.string}),
)


SERVICE_REMOVE_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ID): cv.positive_int,
            vol.Optional(ATTR_DELETE_DATA, default=DEFAULT_DELETE_DATA): cv.boolean,
        }
    )
)

SERVICE_START_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend({vol.Required(CONF_ID): cv.positive_int}),
)

SERVICE_STOP_TORRENT_SCHEMA = vol.All(
    SERVICE_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ID): cv.positive_int,
        }
    )
)

_LOGGER = logging.getLogger(__name__)


def _get_client(
    hass: HomeAssistant, data: dict[str, Any]
) -> TransmissionDataUpdateCoordinator | None:
    """Return client from integration name or entry_id."""
    if (
        (entry_id := data.get(CONF_ENTRY_ID))
        and (entry := hass.config_entries.async_get_entry(entry_id))
        and entry.state == ConfigEntryState.LOADED
    ):
        return hass.data[DOMAIN][entry_id]

    return None


class TransmissionDataUpdateCoordinator(DataUpdateCoordinator[SessionStats]):
    """Transmission dataupdate coordinator class."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: transmission_rpc.Client
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.tm_api = api
        self._tm_data = TransmissionData(hass, entry, api)
        super().__init__(
            hass,
            name="Transmission",
            logger=_LOGGER,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    @property
    def api(self) -> TransmissionData:
        """Return the TransmissionData object."""
        return self._tm_data

    async def _async_update_data(self) -> SessionStats:
        """Update transmission data."""
        return await self.hass.async_add_executor_job(self.api.update)

    async def async_setup(self) -> None:
        """Set up the Transmission client."""
        await self.hass.async_add_executor_job(self.api.init_torrent_list)
        self.add_options()
        self.config_entry.add_update_listener(self.async_options_updated)

    def register_services(self) -> None:
        """Register transmission services."""

        def add_torrent(service: ServiceCall) -> None:
            """Add new torrent to download."""
            if not (tm_client := _get_client(self.hass, service.data)):
                raise ValueError("Transmission instance is not found")

            torrent = service.data[ATTR_TORRENT]
            if torrent.startswith(
                ("http", "ftp:", "magnet:")
            ) or self.hass.config.is_allowed_path(torrent):
                tm_client.tm_api.add_torrent(torrent)
                tm_client.api.update()
            else:
                _LOGGER.warning(
                    "Could not add torrent: unsupported type or no permission"
                )

        def start_torrent(service: ServiceCall) -> None:
            """Start torrent."""
            if not (tm_client := _get_client(self.hass, service.data)):
                raise ValueError("Transmission instance is not found")

            torrent_id = service.data[CONF_ID]
            tm_client.tm_api.start_torrent(torrent_id)
            tm_client.api.update()

        def stop_torrent(service: ServiceCall) -> None:
            """Stop torrent."""
            if not (tm_client := _get_client(self.hass, service.data)):
                raise ValueError("Transmission instance is not found")

            torrent_id = service.data[CONF_ID]
            tm_client.tm_api.stop_torrent(torrent_id)
            tm_client.api.update()

        def remove_torrent(service: ServiceCall) -> None:
            """Remove torrent."""
            if not (tm_client := _get_client(self.hass, service.data)):
                raise ValueError("Transmission instance is not found")

            torrent_id = service.data[CONF_ID]
            delete_data = service.data[ATTR_DELETE_DATA]
            tm_client.tm_api.remove_torrent(torrent_id, delete_data=delete_data)
            tm_client.api.update()

        self.hass.services.async_register(
            DOMAIN, SERVICE_ADD_TORRENT, add_torrent, schema=SERVICE_ADD_TORRENT_SCHEMA
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_TORRENT,
            remove_torrent,
            schema=SERVICE_REMOVE_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_START_TORRENT,
            start_torrent,
            schema=SERVICE_START_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_TORRENT,
            stop_torrent,
            schema=SERVICE_STOP_TORRENT_SCHEMA,
        )

    def add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            scan_interval = self.config_entry.data.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            limit = self.config_entry.data.get(CONF_LIMIT, DEFAULT_LIMIT)
            order = self.config_entry.data.get(CONF_ORDER, DEFAULT_ORDER)
            options = {
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_LIMIT: limit,
                CONF_ORDER: order,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    @staticmethod
    async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Triggered by config entry options updates."""
        tm_client: TransmissionDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        tm_client.update_interval = timedelta(seconds=entry.options[CONF_SCAN_INTERVAL])
        await tm_client.async_request_refresh()


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, api: transmission_rpc.Client
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config = config
        self._api: transmission_rpc.Client = api
        self._session: transmission_rpc.Session | None = None
        self._all_torrents: list[transmission_rpc.Torrent] = []
        self._completed_torrents: list[transmission_rpc.Torrent] = []
        self._started_torrents: list[transmission_rpc.Torrent] = []
        self.torrents: list[transmission_rpc.Torrent] = []

    @property
    def host(self) -> str:
        """Return the host name."""
        return self.config.data[CONF_HOST]

    def update(self) -> SessionStats:
        """Get the latest data from Transmission instance."""
        try:
            data = self._api.session_stats()
            self.torrents = self._api.get_torrents()
            self._session = self._api.get_session()

            self.check_completed_torrent()
            self.check_started_torrent()
            self.check_removed_torrent()
        except transmission_rpc.TransmissionError as err:
            raise UpdateFailed(
                f"Unable to connect to Transmission client {self.host}"
            ) from err

        return data

    def init_torrent_list(self) -> None:
        """Initialize torrent lists."""
        self.torrents = self._api.get_torrents()
        self._completed_torrents = [
            torrent for torrent in self.torrents if torrent.status == "seeding"
        ]
        self._started_torrents = [
            torrent for torrent in self.torrents if torrent.status == "downloading"
        ]

    def check_completed_torrent(self) -> None:
        """Get completed torrent functionality."""
        old_completed_torrent_names = {
            torrent.name for torrent in self._completed_torrents
        }

        current_completed_torrents = [
            torrent for torrent in self.torrents if torrent.status == "seeding"
        ]

        for torrent in current_completed_torrents:
            if torrent.name not in old_completed_torrent_names:
                self.hass.bus.fire(
                    EVENT_DOWNLOADED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._completed_torrents = current_completed_torrents

    def check_started_torrent(self) -> None:
        """Get started torrent functionality."""
        old_started_torrent_names = {torrent.name for torrent in self._started_torrents}

        current_started_torrents = [
            torrent for torrent in self.torrents if torrent.status == "downloading"
        ]

        for torrent in current_started_torrents:
            if torrent.name not in old_started_torrent_names:
                self.hass.bus.fire(
                    EVENT_STARTED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._started_torrents = current_started_torrents

    def check_removed_torrent(self) -> None:
        """Get removed torrent functionality."""
        current_torrent_names = {torrent.name for torrent in self.torrents}

        for torrent in self._all_torrents:
            if torrent.name not in current_torrent_names:
                self.hass.bus.fire(
                    EVENT_REMOVED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._all_torrents = self.torrents.copy()

    def start_torrents(self) -> None:
        """Start all torrents."""
        if not self.torrents:
            return
        self._api.start_all()

    def stop_torrents(self) -> None:
        """Stop all active torrents."""
        if not self.torrents:
            return
        torrent_ids = [torrent.id for torrent in self.torrents]
        self._api.stop_torrent(torrent_ids)

    def set_alt_speed_enabled(self, is_enabled: bool) -> None:
        """Set the alternative speed flag."""
        self._api.set_session(alt_speed_enabled=is_enabled)

    def get_alt_speed_enabled(self) -> bool | None:
        """Get the alternative speed flag."""
        if self._session is None:
            return None

        return self._session.alt_speed_enabled
