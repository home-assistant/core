"""Support for the Transmission BitTorrent client API."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
import logging
import re
from typing import Any

import transmission_rpc
from transmission_rpc.error import (
    TransmissionAuthError,
    TransmissionConnectError,
    TransmissionError,
)
from transmission_rpc.session import SessionStats
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector,
)
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
    CONF_ENTRY_ID,
    CONF_LIMIT,
    CONF_ORDER,
    DATA_UPDATED,
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
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)


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

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

MIGRATION_NAME_TO_KEY = {
    # Sensors
    "Down Speed": "download",
    "Up Speed": "upload",
    "Status": "status",
    "Active Torrents": "active_torrents",
    "Paused Torrents": "paused_torrents",
    "Total Torrents": "total_torrents",
    "Completed Torrents": "completed_torrents",
    "Started Torrents": "started_torrents",
    # Switches
    "Switch": "on_off",
    "Turtle Mode": "turtle_mode",
}


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Transmission Component."""

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        """Update unique ID of entity entry."""
        match = re.search(
            f"{config_entry.data[CONF_HOST]}-{config_entry.data[CONF_NAME]} (?P<name>.+)",
            entity_entry.unique_id,
        )

        if match and (key := MIGRATION_NAME_TO_KEY.get(match.group("name"))):
            return {"new_unique_id": f"{config_entry.entry_id}-{key}"}
        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    try:
        api = await get_api(hass, dict(config_entry.data))
    except CannotConnect as error:
        raise ConfigEntryNotReady from error
    except (AuthenticationError, UnknownError) as error:
        raise ConfigEntryAuthFailed from error

    client = TransmissionClient(hass, config_entry, api)
    await client.async_setup()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    client.register_services()
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Transmission Entry from config_entry."""
    client: TransmissionClient = hass.data[DOMAIN].pop(config_entry.entry_id)
    if client.unsub_timer:
        client.unsub_timer()

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_START_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_STOP_TORRENT)

    return unload_ok


async def get_api(
    hass: HomeAssistant, entry: dict[str, Any]
) -> transmission_rpc.Client:
    """Get Transmission client."""
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        api = await hass.async_add_executor_job(
            partial(
                transmission_rpc.Client,
                username=username,
                password=password,
                host=host,
                port=port,
            )
        )
        _LOGGER.debug("Successfully connected to %s", host)
        return api

    except TransmissionAuthError as error:
        _LOGGER.error("Credentials for Transmission client are not valid")
        raise AuthenticationError from error
    except TransmissionConnectError as error:
        _LOGGER.error("Connecting to the Transmission client %s failed", host)
        raise CannotConnect from error
    except TransmissionError as error:
        _LOGGER.error(error)
        raise UnknownError from error


def _get_client(hass: HomeAssistant, data: dict[str, Any]) -> TransmissionClient | None:
    """Return client from integration name or entry_id."""
    if (
        (entry_id := data.get(CONF_ENTRY_ID))
        and (entry := hass.config_entries.async_get_entry(entry_id))
        and entry.state == ConfigEntryState.LOADED
    ):
        return hass.data[DOMAIN][entry_id]

    return None


class TransmissionClient:
    """Transmission Client Object."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: transmission_rpc.Client,
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config_entry = config_entry
        self.tm_api = api
        self._tm_data = TransmissionData(self.hass, self.config_entry, api)
        self.unsub_timer: Callable[[], None] | None = None

    @property
    def api(self) -> TransmissionData:
        """Return the TransmissionData object."""
        return self._tm_data

    async def async_setup(self) -> None:
        """Set up the Transmission client."""
        await self.hass.async_add_executor_job(self.api.init_torrent_list)
        await self.hass.async_add_executor_job(self.api.update)
        self.add_options()
        self.set_scan_interval(self.config_entry.options[CONF_SCAN_INTERVAL])

    def register_services(self) -> None:
        """Register integration services."""

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

        self.config_entry.add_update_listener(self.async_options_updated)

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

    def set_scan_interval(self, scan_interval: float) -> None:
        """Update scan interval."""

        def refresh(event_time: datetime) -> None:
            """Get the latest data from Transmission."""
            self.api.update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, refresh, timedelta(seconds=scan_interval)
        )

    @staticmethod
    async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Triggered by config entry options updates."""
        tm_client: TransmissionClient = hass.data[DOMAIN][entry.entry_id]
        tm_client.set_scan_interval(entry.options[CONF_SCAN_INTERVAL])
        await hass.async_add_executor_job(tm_client.api.update)


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigEntry, api: transmission_rpc.Client
    ) -> None:
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config = config
        self._api: transmission_rpc.Client = api
        self.data: SessionStats | None = None
        self.available: bool = True
        self._session: transmission_rpc.Session | None = None
        self._all_torrents: list[transmission_rpc.Torrent] = []
        self._completed_torrents: list[transmission_rpc.Torrent] = []
        self._started_torrents: list[transmission_rpc.Torrent] = []
        self._torrents: list[transmission_rpc.Torrent] = []

    @property
    def host(self) -> str:
        """Return the host name."""
        return self.config.data[CONF_HOST]

    @property
    def signal_update(self) -> str:
        """Update signal per transmission entry."""
        return f"{DATA_UPDATED}-{self.host}"

    @property
    def torrents(self) -> list[transmission_rpc.Torrent]:
        """Get the list of torrents."""
        return self._torrents

    def update(self) -> None:
        """Get the latest data from Transmission instance."""
        try:
            self.data = self._api.session_stats()
            self._torrents = self._api.get_torrents()
            self._session = self._api.get_session()

            self.check_completed_torrent()
            self.check_started_torrent()
            self.check_removed_torrent()
            _LOGGER.debug("Torrent Data for %s Updated", self.host)

            self.available = True
        except TransmissionError:
            self.available = False
            _LOGGER.error("Unable to connect to Transmission client %s", self.host)
        dispatcher_send(self.hass, self.signal_update)

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

    def get_alt_speed_enabled(self) -> bool | None:
        """Get the alternative speed flag."""
        if self._session is None:
            return None

        return self._session.alt_speed_enabled
