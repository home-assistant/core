"""Transmission Client class."""
from __future__ import annotations

from datetime import timedelta
from functools import partial
import logging
from typing import Any

import transmissionrpc
from transmissionrpc.error import TransmissionError
from transmissionrpc.session import Session
from transmissionrpc.torrent import Torrent
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
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
from .errors import (
    AuthenticationError,
    CannotConnect,
    TransmissionrBaseError,
    UnknownError,
)

_LOGGER = logging.getLogger(__name__)


SERVICE_ADD_TORRENT_SCHEMA = vol.Schema(
    {vol.Required(ATTR_TORRENT): cv.string, vol.Required(CONF_NAME): cv.string}
)

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
    }
)
SERVICE_REMOVE_TORRENT_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_DELETE_DATA, default=DEFAULT_DELETE_DATA): cv.boolean,
    }
)


async def get_api(hass: HomeAssistant, entry: dict[str, Any]) -> transmissionrpc.Client:
    """Get Transmission client."""
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        api: transmissionrpc.Client = await hass.async_add_executor_job(
            transmissionrpc.Client, host, port, username, password
        )
        _LOGGER.debug("Successfully connected to %s", host)
        return api

    except TransmissionError as error:
        if "401: Unauthorized" in str(error):
            _LOGGER.error("Credentials for Transmission client are not valid")
            raise AuthenticationError from error
        if "111: Connection refused" in str(error):
            _LOGGER.error("Connecting to the Transmission client %s failed", host)
            raise CannotConnect from error

        _LOGGER.error(error)
        raise UnknownError from error


class TransmissionClientCoordinator(DataUpdateCoordinator):
    """Transmission Client Object."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self._tm_data: TransmissionData | None = None
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )

    @property
    def tm_data(self):
        """Return the TransmissionData object."""
        return self._tm_data

    async def async_update(self) -> Session:
        """Update Speedtest data."""
        try:
            return await self.hass.async_add_executor_job(self.tm_data.update)
        except TransmissionError as err:
            raise UpdateFailed(
                f"Unable to connect to Transmission client {self.config_entry.data[CONF_HOST]}",
            ) from err

    async def async_setup(self) -> None:
        """Set up the Transmission client."""

        try:
            tm_api = await get_api(self.hass, {**self.config_entry.data})
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except TransmissionrBaseError as error:
            raise ConfigEntryNotReady from error

        self.add_options()
        self._tm_data = TransmissionData(self.hass, self.config_entry, tm_api)
        await self.hass.async_add_executor_job(self._tm_data.init_torrent_list)

        async def async_add_torrent(service: ServiceCall) -> None:
            """Add new torrent to download."""
            tm_client: TransmissionClientCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            torrent: str = service.data[ATTR_TORRENT]
            if torrent.startswith(
                ("http", "ftp:", "magnet:")
            ) or self.hass.config.is_allowed_path(torrent):
                await self.hass.async_add_executor_job(
                    tm_client.tm_data.api.add_torrent, torrent
                )
                await tm_client.async_request_refresh()
            else:
                _LOGGER.warning(
                    "Could not add torrent: unsupported type or no permission"
                )

        async def async_start_torrent(service: ServiceCall) -> None:
            """Start torrent."""
            tm_client: TransmissionClientCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            await self.hass.async_add_executor_job(
                tm_client.tm_data.api.start_torrent, service.data[CONF_ID]
            )
            await tm_client.async_request_refresh()

        async def async_stop_torrent(service: ServiceCall) -> None:
            """Stop torrent."""
            tm_client: TransmissionClientCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            await self.hass.async_add_executor_job(
                tm_client.tm_data.api.stop_torrent, service.data[CONF_ID]
            )
            await tm_client.async_request_refresh()

        async def async_remove_torrent(service: ServiceCall) -> None:
            """Remove torrent."""
            tm_client: TransmissionClientCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            await self.hass.async_add_executor_job(
                partial(
                    tm_client.tm_data.api.remove_torrent,
                    service.data[CONF_ID],
                    delete_data=service.data[ATTR_DELETE_DATA],
                )
            )
            await tm_client.async_request_refresh()

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            async_add_torrent,
            schema=SERVICE_ADD_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_TORRENT,
            async_remove_torrent,
            schema=SERVICE_REMOVE_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_START_TORRENT,
            async_start_torrent,
            schema=SERVICE_BASE_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_TORRENT,
            async_stop_torrent,
            schema=SERVICE_BASE_SCHEMA,
        )

        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(self.async_options_updated)
        )

    def add_options(self) -> None:
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
        tm_client: TransmissionClientCoordinator = hass.data[DOMAIN][entry.entry_id]
        tm_client.update_interval = timedelta(seconds=entry.options[CONF_SCAN_INTERVAL])
        await tm_client.async_request_refresh()


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, api: transmissionrpc.Client
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config: ConfigEntry = config
        self.api = api
        self._torrents: list[Torrent] = []
        self._all_torrents: list[Torrent] = []
        self._started_torrents: list[Torrent] = []
        self._completed_torrents: list[Torrent] = []

    @property
    def torrents(self) -> list[Torrent]:
        """Get the list of torrents."""
        return self._torrents

    def update(self) -> Session:
        """Get the latest data from Transmission instance."""
        self.api.session_stats()
        self._torrents = self.api.get_torrents()
        self.check_completed_torrent()
        self.check_started_torrent()
        self.check_removed_torrent()
        return self.api.get_session()

    def init_torrent_list(self) -> None:
        """Initialize torrent lists."""
        self._torrents = self.api.get_torrents()
        self._completed_torrents = [
            torrent for torrent in self._torrents if torrent.status == "seeding"
        ]
        self._started_torrents = [
            torrent for torrent in self._torrents if torrent.status == "downloading"
        ]

    def check_completed_torrent(self) -> None:
        """Get completed torrent functionality."""
        old_completed_torrent_names = {
            torrent.name for torrent in self._completed_torrents
        }

        current_completed_torrents = [
            torrent for torrent in self._torrents if torrent.status == "seeding"
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
            torrent for torrent in self._torrents if torrent.status == "downloading"
        ]

        for torrent in current_started_torrents:
            if torrent.name not in old_started_torrent_names:
                self.hass.bus.fire(
                    EVENT_STARTED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._started_torrents = current_started_torrents

    def check_removed_torrent(self) -> None:
        """Get removed torrent functionality."""
        current_torrent_names = {torrent.name for torrent in self._torrents}

        for torrent in self._all_torrents:
            if torrent.name not in current_torrent_names:
                self.hass.bus.fire(
                    EVENT_REMOVED_TORRENT, {"name": torrent.name, "id": torrent.id}
                )

        self._all_torrents = self._torrents.copy()

    def start_torrents(self) -> None:
        """Start all torrents."""
        if len(self._torrents) <= 0:
            return
        self.api.start_all()

    def stop_torrents(self) -> None:
        """Stop all active torrents."""
        torrent_ids = [torrent.id for torrent in self._torrents]
        self.api.stop_torrent(torrent_ids)

    def set_alt_speed_enabled(self, is_enabled: bool) -> None:
        """Set the alternative speed flag."""
        self.api.set_session(alt_speed_enabled=is_enabled)
