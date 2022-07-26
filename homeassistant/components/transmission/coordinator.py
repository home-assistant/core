"""Transmission Client class."""
from __future__ import annotations

from datetime import timedelta
from functools import partial
import logging
from typing import Any

import transmissionrpc
from transmissionrpc.error import TransmissionError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
    DEFAULT_DELETE_DATA,
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
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)


SERVICE_ADD_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TORRENT): cv.string,
        vol.Required(CONF_NAME): cv.string,
    }
)

SERVICE_REMOVE_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(ATTR_DELETE_DATA, default=DEFAULT_DELETE_DATA): cv.boolean,
    }
)

SERVICE_START_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): vol.Any(cv.positive_int, [cv.positive_int]),
    }
)

SERVICE_STOP_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
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


class TransmissionDataUpdateCoordinator(DataUpdateCoordinator[transmissionrpc.Session]):
    """Transmission coordinator object."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: transmissionrpc.Client,
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.tm_api = api
        self._tm_data = TransmissionData(hass, config_entry, api)
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def api(self):
        """Return the TransmissionData object."""
        return self._tm_data

    async def async_update(self) -> transmissionrpc.Session:
        """Update Speedtest data."""
        try:
            return await self.hass.async_add_executor_job(self.api.update)
        except TransmissionError as err:
            raise UpdateFailed(
                f"Unable to connect to Transmission client {self.config_entry.data[CONF_HOST]}"
            ) from err

    async def async_setup(self) -> None:
        """Set up the Transmission client."""

        await self.hass.async_add_executor_job(self._tm_data.init_torrent_list)

        async def async_add_torrent(service: ServiceCall) -> None:
            """Add new torrent to download."""
            tm_client: TransmissionDataUpdateCoordinator | None = None
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
                torrent = await self.hass.async_add_executor_job(
                    tm_client.api.add_torrent,
                    torrent,
                )
                await tm_client.async_request_refresh()
            else:
                _LOGGER.warning(
                    "Could not add torrent: unsupported type or no permission"
                )

        async def async_start_torrent(service: ServiceCall) -> None:
            """Start torrent."""
            tm_client: TransmissionDataUpdateCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            torrent_id = service.data[CONF_ID]
            await self.hass.async_add_executor_job(
                tm_client.api.start_torrent, torrent_id
            )
            await tm_client.async_request_refresh()

        async def async_stop_torrent(service: ServiceCall) -> None:
            """Stop torrent."""
            tm_client: TransmissionDataUpdateCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            torrent_id = service.data[CONF_ID]
            await self.hass.async_add_executor_job(
                tm_client.api.stop_torrent, torrent_id
            )
            await tm_client.async_request_refresh()

        async def async_remove_torrent(service: ServiceCall) -> None:
            """Remove torrent."""
            tm_client: TransmissionDataUpdateCoordinator | None = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    tm_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if tm_client is None:
                _LOGGER.error("Transmission instance is not found")
                return
            torrent_id = service.data[CONF_ID]
            delete_data = service.data[ATTR_DELETE_DATA]
            await self.hass.async_add_executor_job(
                partial(
                    tm_client.api.remove_torrent,
                    torrent_id,
                    delete_data=delete_data,
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
            schema=SERVICE_START_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_TORRENT,
            async_stop_torrent,
            schema=SERVICE_STOP_TORRENT_SCHEMA,
        )


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, api: transmissionrpc.Client
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config: ConfigEntry = config
        self._all_torrents: list[transmissionrpc.Torrent] = []
        self._api = api
        self._completed_torrents: list[transmissionrpc.Torrent] = []
        self._started_torrents: list[transmissionrpc.Torrent] = []
        self._torrents: list[transmissionrpc.Torrent] = []

    @property
    def torrents(self) -> list[transmissionrpc.Torrent]:
        """Get the list of torrents."""
        return self._torrents

    def update(self) -> transmissionrpc.Session:
        """Get the latest data from Transmission instance."""
        self._api.session_stats()
        self._torrents = self._api.get_torrents()
        self.check_completed_torrent()
        self.check_started_torrent()
        self.check_removed_torrent()
        return self._api.get_session()

    def init_torrent_list(self) -> None:
        """Initialize torrent lists."""
        self._torrents = self._api.get_torrents()
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
        if not self._torrents:
            return
        self._api.start_all()

    def stop_torrents(self) -> None:
        """Stop all active torrents."""
        if not self._torrents:
            return
        torrent_ids = [torrent.id for torrent in self._torrents]
        self._api.stop_torrent(torrent_ids)

    def set_alt_speed_enabled(self, is_enabled: bool) -> None:
        """Set the alternative speed flag."""
        self._api.set_session(alt_speed_enabled=is_enabled)
