"""Support for the Deluge BitTorrent client API."""
from __future__ import annotations

from datetime import timedelta
import logging

from deluge_client import DelugeRPCClient, FailedToReconnectException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_DELETE_DATA,
    ATTR_TORRENT,
    CONF_LIMIT,
    CONF_ORDER,
    DATA_UPDATED,
    DEFAULT_DELETE_DATA,
    DEFAULT_LIMIT,
    DEFAULT_NAME,
    DEFAULT_ORDER,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_STARTED_TORRENT,
    EVENT_FINISHED_TORRENT,
    EVENT_ADDED_TORRENT,
    EVENT_REMOVED_TORRENT,
    SERVICE_ADD_TORRENT,
    SERVICE_RESUME_TORRENT,
    SERVICE_PAUSE_TORRENT,
    SERVICE_REMOVE_TORRENT,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)


SERVICE_ADD_TORRENT_SCHEMA = vol.Schema(
    {vol.Required(ATTR_TORRENT): cv.string, vol.Required(CONF_NAME): cv.string}
)

SERVICE_START_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
    }
)

SERVICE_STOP_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
    }
)

SERVICE_REMOVE_TORRENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(ATTR_DELETE_DATA, default=DEFAULT_DELETE_DATA): cv.boolean,
    }
)

DELUGE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): cv.time_period,
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(cv.deprecated(DOMAIN), {DOMAIN: vol.All(cv.ensure_list, [DELUGE_SCHEMA])}),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["sensor", "switch"]


async def async_setup(hass, config):
    """Import the Deluge Component from config."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Deluge Component."""
    client = DelugeClient(hass, config_entry)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = client

    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Deluge Entry from config_entry."""
    client = hass.data[DOMAIN].pop(config_entry.entry_id)
    if client.unsub_timer:
        client.unsub_timer()

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_RESUME_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_PAUSE_TORRENT)
        hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TORRENT)

    return unload_ok


async def get_client(hass, entry):
    """Get Deluge client."""
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        api = await hass.async_add_executor_job(
            DelugeRPCClient, host, port, username, password
        )
        _LOGGER.debug("Successfully connected to %s", host)
        return api

    except FailedToReconnectException as error:
        """
        if "401: Unauthorized" in str(error):
            _LOGGER.error("Credentials for Deluge client are not valid")
            raise AuthenticationError from error
        if "111: Connection refused" in str(error):
            _LOGGER.error("Connecting to the Deluge client %s failed", host)
            raise CannotConnect from error
        """

        _LOGGER.error(error)
        raise UnknownError from error


class DelugeClient:
    """Deluge Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Deluge RPC API."""
        self.hass = hass
        self.config_entry = config_entry
        self.deluge_client: DelugeRPCClient = None
        self._deluge_state: DelugeState = None
        self.unsub_timer = None

    @property
    def state(self) -> DelugeState:
        """Return the DelugeData object."""
        return self._deluge_state

    async def async_setup(self):
        """Set up the Deluge client."""

        try:
            self.deluge_client = await get_client(self.hass, self.config_entry.data)
        except CannotConnect as error:
            raise ConfigEntryNotReady from error
        except (AuthenticationError, UnknownError):
            return False

        self._deluge_state = DelugeState(
            self.hass, self.config_entry, self.deluge_client
        )

        await self.hass.async_add_executor_job(self._deluge_state.init_torrents)
        await self.hass.async_add_executor_job(self._deluge_state.update)
        self.add_options()
        self.set_scan_interval(self.config_entry.options[CONF_SCAN_INTERVAL])

        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

        def _get_deluge_client(service):
            deluge_client = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_NAME] == service.data[CONF_NAME]:
                    deluge_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if deluge_client is None:
                _LOGGER.error("Deluge instance is not found")
                return None
            return deluge_client

        def add_torrent(service):
            """Add new torrent to download."""
            deluge_client = _get_deluge_client(service)
            if not deluge_client:
                return
            torrent = service.data[ATTR_TORRENT]
            if torrent.startswith(
                ("magnet:", "http:", "https:", "ftp:")
            ) or self.hass.config.is_allowed_path(torrent):
                if torrent.startswith("magnet:"):
                    deluge_client.deluge_client.call("core.add_torrent_magnet", torrent)
                else:
                    deluge_client.deluge_client.call("core.add_torrent_url", torrent)
                deluge_client.state.update()
            else:
                _LOGGER.warning(
                    "Could not add torrent: unsupported type or no permission"
                )

        def resume_torrent(service):
            """Start torrent."""
            deluge_client = _get_deluge_client(service)
            if not deluge_client:
                return
            torrent_id = service.data[CONF_ID]
            deluge_client.deluge_client.call("core.resume_torrent", torrent_id)
            deluge_client.state.update()

        def pause_torrent(service):
            """Stop torrent."""
            deluge_client = _get_deluge_client(service)
            if not deluge_client:
                return
            torrent_id = service.data[CONF_ID]
            deluge_client.deluge_client.call("core.pause_torrent", torrent_id)
            deluge_client.state.update()

        def remove_torrent(service):
            """Remove torrent."""
            deluge_client = _get_deluge_client(service)
            if not deluge_client:
                return
            torrent_id = service.data[CONF_ID]
            delete_data = service.data[ATTR_DELETE_DATA]
            deluge_client.deluge_client.call(
                "core.remove_torrent", torrent_id, delete_data
            )
            deluge_client.state.update()

        self.hass.services.async_register(
            DOMAIN, SERVICE_ADD_TORRENT, add_torrent, schema=SERVICE_ADD_TORRENT_SCHEMA
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_RESUME_TORRENT,
            resume_torrent,
            schema=SERVICE_START_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_PAUSE_TORRENT,
            pause_torrent,
            schema=SERVICE_STOP_TORRENT_SCHEMA,
        )

        self.hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_TORRENT,
            remove_torrent,
            schema=SERVICE_REMOVE_TORRENT_SCHEMA,
        )

        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    def add_options(self):
        """Add options for entry."""
        if self.config_entry.options:
            return
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

        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    def set_scan_interval(self, scan_interval):
        """Update scan interval."""

        def refresh(_):
            """Get the latest data from Deluge."""
            self._deluge_state.update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, refresh, timedelta(seconds=scan_interval)
        )

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        deluge_client = hass.data[DOMAIN][entry.entry_id]
        deluge_client.set_scan_interval(entry.options[CONF_SCAN_INTERVAL])
        await hass.async_add_executor_job(deluge_client.api.update)


class DelugeState:
    """Get the latest data and update the states."""

    def __init__(self, hass, config, client: DelugeRPCClient):
        """Initialize the Deluge RPC API."""
        self.hass = hass
        self.config = config
        self.available: bool = True
        self._client: DelugeRPCClient = client
        self._session: dict = None
        self._torrents: list[dict] = []

    @property
    def host(self):
        """Return the host name."""
        return self.config.data[CONF_HOST]

    @property
    def signal_update(self):
        """Update signal per Deluge entry."""
        return f"{DATA_UPDATED}-{self.host}"

    @property
    def session(self):
        """Get the session data."""
        return self._session

    @property
    def torrents(self):
        """Get the list of torrents."""
        return self._torrents

    def init_torrents(self):
        """Initialize torrent list."""
        self._torrents = self._get_torrents_status()

    def update(self):
        """Get the latest data from Deluge instance."""
        try:
            self._session = self._get_session_status()
            old_torrents, self._torrents = self._torrents, self._get_torrents_status()

            self._fire_status_change_events(old_torrents)
            self._fire_existence_events(old_torrents)

            _LOGGER.debug("Torrent Data for %s Updated", self.host)
            self.available = True

        except FailedToReconnectException:
            self.available = False
            _LOGGER.error("Unable to connect to Deluge client %s", self.host)

        dispatcher_send(self.hass, self.signal_update)

    def resume_torrents(self):
        """Start all torrents."""
        if not self._torrents:
            return
        torrent_ids = [torrent[b"id"] for torrent in self._torrents]
        self._client.call("core.resume_torrent", torrent_ids)

    def pause_torrents(self):
        """Stop all active torrents."""
        if not self._torrents:
            return
        torrent_ids = [torrent[b"id"] for torrent in self._torrents]
        self._client.call("core.pause_torrent", torrent_ids)

    def _get_session_status(self):
        session_status = self._client.call(
            "core.get_session_status",
            [
                "dht_download_rate",
                "dht_upload_rate",
                "download_rate",
                "upload_rate",
            ],
        )
        session_status[b"free_space"] = self._client.call("core.get_free_space")
        return session_status

    def _get_torrents_status(self, states=None):
        torrents_status = self._client.call(
            "core.get_torrents_status",
            {"state": states} if states else None,
            ["eta", "name", "progress", "ratio", "state", "time_added"],
        )
        for torrent_id, torrent_info in torrents_status.items():
            torrent_info[b"id"] = torrent_id
        return list(torrents_status.values())

    def _fire_status_change_events(self, old_torrents):
        old_torrent_states = {
            torrent_info[b"id"]: torrent_info[b"state"] for torrent_info in old_torrents
        }

        current_torrents = {
            torrent_info[b"id"]: torrent_info for torrent_info in self._torrents
        }

        for torrent_id, torrent_info in current_torrents.items():
            old_torrent_state = old_torrent_states.get(torrent_id)
            torrent_state = torrent_info[b"state"]
            if (
                b"Downloading" not in (old_torrent_state, torrent_state)
                or old_torrent_state == torrent_state
            ):
                continue
            event_type = (
                EVENT_STARTED_TORRENT
                if torrent_state == b"Downloading"
                else EVENT_FINISHED_TORRENT
            )
            event_state = (
                "Started" if event_type == EVENT_STARTED_TORRENT else "Finished"
            )
            self.hass.bus.fire(
                event_type,
                {
                    "id": torrent_id.decode("ascii"),
                    "name": torrent_info[b"name"].decode("ascii"),
                    "state": event_state,
                },
            )

    def _fire_existence_events(self, old_torrents):
        old_torrent_names = {
            torrent_info[b"id"]: torrent_info[b"name"] for torrent_info in old_torrents
        }

        current_torrent_names = {
            torrent_info[b"id"]: torrent_info[b"name"]
            for torrent_info in self._torrents
        }

        for torrent_id, torrent_name in current_torrent_names.items():
            if torrent_id in old_torrent_names:
                continue
            self.hass.bus.fire(
                EVENT_ADDED_TORRENT,
                {
                    "id": torrent_id.decode("ascii"),
                    "name": torrent_name.decode("ascii"),
                    "state": "Added",
                },
            )

        for torrent_id, torrent_name in old_torrent_names.items():
            if torrent_id in current_torrent_names:
                continue
            self.hass.bus.fire(
                EVENT_REMOVED_TORRENT,
                {
                    "id": torrent_id.decode("ascii"),
                    "name": torrent_name.decode("ascii"),
                    "state": "Removed",
                },
            )
