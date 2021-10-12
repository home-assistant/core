"""Support for the Deluge BitTorrent client API."""
from __future__ import annotations

from datetime import timedelta
import logging

from deluge_client import DelugeRPCClient, FailedToReconnectException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
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
    DATA_UPDATED,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)


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

    return unload_ok


async def get_client(hass, entry):
    """Get Deluge client."""
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        client = await hass.async_add_executor_job(
            _make_client, host, port, username, password
        )
        _LOGGER.debug("Successfully connected to %s", host)
        return client

    except ConnectionError as error:
        _LOGGER.error("Connecting to the Deluge client %s failed", host)
        raise CannotConnect from error

    except Exception as error:
        if type(error).__name__ == 'BadLoginError':
            _LOGGER.error("Credentials for Deluge client are not valid")
            raise AuthenticationError from error

        _LOGGER.error(error)
        raise UnknownError from error


def _make_client(host, port, username, password):
    client = DelugeRPCClient(host, port, username, password)
    client.connect()
    return client


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

        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    def add_options(self):
        """Add options for entry."""
        if self.config_entry.options:
            return
        scan_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        options = {
            CONF_SCAN_INTERVAL: scan_interval,
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
        self._session: dict = {}
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
            self._torrents = self._get_torrents_status()

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
