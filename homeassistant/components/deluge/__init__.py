"""The Deluge integration."""
from datetime import timedelta
import logging

from deluge_client import DelugeRPCClient, FailedToReconnectException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_TORRENT,
    DATA_UPDATED,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_ADD_TORRENT,
)
from .errors import CannotConnect, PasswordError, UserNameError, UnknownError

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
    {DOMAIN: vol.All(cv.ensure_list, [DELUGE_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["sensor", "switch"]

SERVICE_ADD_TORRENT_SCHEMA = vol.Schema(
    {vol.Required(ATTR_TORRENT): cv.string, vol.Required(CONF_HOST): cv.string}
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Import the Deluge component from config."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Deluge from a config entry."""
    client = DelugeClient(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    client = hass.data[DOMAIN].pop(entry.entry_id)
    if client.unsub_timer:
        client.unsub_timer()

    return True


async def get_api(hass, entry):
    """Get Transmission client."""
    host = entry[CONF_HOST]
    port = entry[CONF_PORT]
    username = entry.get(CONF_USERNAME)
    password = entry.get(CONF_PASSWORD)

    try:
        api = await hass.async_add_executor_job(
            DelugeRPCClient, host, port, username, password, True
        )
        api.connect()
        _LOGGER.debug("Successfully connected to %s", host)
        return api

    except ConnectionRefusedError as error:
        _LOGGER.error(error)
        raise CannotConnect
    except Exception as error:  # pylint: disable=broad-except
        _LOGGER.error(error)
        if "Username does not exist" in str(error):
            raise UserNameError
        if "Password does not match" in str(error):
            raise PasswordError
        raise UnknownError


class DelugeClient:
    """Deluge Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Deluge client."""
        self.hass = hass
        self.config_entry = config_entry
        self._deluge_data = None
        self.unsub_timer = None

    @property
    def api(self):
        """Return the _deluge_data object."""
        return self._deluge_data

    async def async_setup(self):
        """Set up the Deluge client."""

        try:
            deluge_api = await get_api(self.hass, self.config_entry.data)
        except CannotConnect:
            raise ConfigEntryNotReady
        except (UserNameError, PasswordError, UnknownError):
            return False

        self._deluge_data = DelugeData(self.hass, self.config_entry, deluge_api)

        await self.hass.async_add_executor_job(self._deluge_data.init_torrent_list)
        await self.hass.async_add_executor_job(self._deluge_data.update)
        self.add_options()
        self.set_scan_interval(self.config_entry.options[CONF_SCAN_INTERVAL])

        for component in PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component
                )
            )

        def add_torrent(service):
            """Add new torrent to download."""
            torrent = service.data[ATTR_TORRENT]
            deluge_client = None
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == service.data[CONF_HOST]:
                    deluge_client = self.hass.data[DOMAIN][entry.entry_id]
                    break
            if deluge_client is None:
                _LOGGER.error("Deluge host is not found")
                return
            if torrent.startswith(("http", "ftp:")):
                deluge_api.core.add_torrent_url(torrent, {})
            elif torrent.startswith(("magnet:")):
                deluge_api.core.add_torrent_magnet(torrent, {})
            else:
                _LOGGER.warning("Could not add torrent: unsupported type")

        self.hass.services.async_register(
            DOMAIN, SERVICE_ADD_TORRENT, add_torrent, schema=SERVICE_ADD_TORRENT_SCHEMA
        )

        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    def add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            scan_interval = self.config_entry.data.pop(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            options = {CONF_SCAN_INTERVAL: scan_interval}

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    def set_scan_interval(self, scan_interval):
        """Update scan interval."""

        def refresh(event_time):
            """Get the latest data from Transmission."""
            self._deluge_data.update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, refresh, timedelta(seconds=scan_interval)
        )

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        hass.data[DOMAIN][entry.entry_id].set_scan_interval(
            entry.options[CONF_SCAN_INTERVAL]
        )


class DelugeData:
    """Get the latest data and update the states."""

    def __init__(self, hass, config, api):
        """Initialize the Deluge Data object."""
        self.hass = hass
        self.config = config
        self.data = None
        self.torrents = None
        self.session = None
        self.available = True
        self._api = api
        self.completed_torrents = []
        self.started_torrents = []

    @property
    def host(self):
        """Return the host name."""
        return self.config.data[CONF_HOST]

    @property
    def signal_update(self):
        """Update signal per deluge entry."""
        return f"{DATA_UPDATED}-{self.host}"

    def update(self):
        """Get the latest data from deluge instance."""
        try:
            self.data = self._api.core.get_session_status(
                [
                    "upload_rate",
                    "download_rate",
                    "dht_upload_rate",
                    "dht_download_rate",
                ],
            )
            self.torrents = self._api.core.get_torrents_status({}, ["name", "state"])
            self.check_completed_torrent()
            self.check_started_torrent()
            _LOGGER.debug("Torrent Data for %s Updated", self.host)

            self.available = True
        except FailedToReconnectException:
            self.available = False
            _LOGGER.error("Unable to connect to Deeluge client %s", self.host)

        dispatcher_send(self.hass, self.signal_update)

    def init_torrent_list(self):
        """Initialize torrent lists."""
        self.torrents = self._api.core.get_torrents_status({}, ["name", "state"])
        self.completed_torrents = [
            self.torrents[var]["name"]
            for var in self.torrents
            if self.torrents[var]["state"] == "Seeding"
        ]
        self.started_torrents = [
            self.torrents[var]["name"]
            for var in self.torrents
            if self.torrents[var]["state"] == "Downloading"
        ]

    def check_completed_torrent(self):
        """Get completed torrent functionality."""
        completed_torrents = [
            self.torrents[var]["name"]
            for var in self.torrents
            if self.torrents[var]["state"] == "Seeding"
        ]

        tmp_completed_torrents = list(
            set(completed_torrents).difference(self.completed_torrents)
        )

        for var in tmp_completed_torrents:
            self.hass.bus.fire("deluge_downloaded_torrent", {"name": var})

        self.completed_torrents = completed_torrents

    def check_started_torrent(self):
        """Get started torrent functionality."""
        started_torrents = [
            self.torrents[var]["name"]
            for var in self.torrents
            if self.torrents[var]["state"] == "Downloading"
        ]

        tmp_started_torrents = list(
            set(started_torrents).difference(self.started_torrents)
        )

        for var in tmp_started_torrents:
            self.hass.bus.fire("deluge_started_torrent", {"name": var})
        self.started_torrents = started_torrents

    def get_torrents_count(self):
        """Get the number of all torrents."""
        return len(self.torrents)

    def get_started_torrent_count(self):
        """Get the number of started torrents."""
        return len(self.started_torrents)

    def get_completed_torrent_count(self):
        """Get the number of completed torrents."""
        return len(self.completed_torrents)

    def get_paused_torrents_count(self):
        """Get the number of paused torrents."""
        paused_torrents = [
            self.torrents[var]["name"]
            for var in self.torrents
            if self.torrents[var]["state"] == "Paused"
        ]
        return len(paused_torrents)

    def get_active_torrents_count(self):
        """Get the number of active torrents."""
        active_torrents = [
            self.torrents[var]["name"]
            for var in self.torrents
            if self.torrents[var]["state"] in ["Seeding", "Downloading"]
        ]
        return len(active_torrents)

    def start_torrents(self):
        """Start all torrents."""
        torrent_ids = self._api.core.get_session_state()
        self._api.core.resume_torrents(torrent_ids)

    def stop_torrents(self):
        """Stop all active torrents."""
        torrent_ids = self._api.core.get_session_state()
        self._api.core.pause_torrents(torrent_ids)
