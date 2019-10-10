"""Support for the Transmission BitTorrent client API."""
from datetime import timedelta
import logging

import transmissionrpc
from transmissionrpc.error import TransmissionError
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
    ATTR_TORRENT,
    DATA_TRANSMISSION,
    DATA_UPDATED,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_ADD_TORRENT,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

_LOGGER = logging.getLogger(__name__)


SERVICE_ADD_TORRENT_SCHEMA = vol.Schema({vol.Required(ATTR_TORRENT): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Import the Transmission Component from config."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Transmission Component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if not config_entry.options:
        await async_populate_options(hass, config_entry)

    client = TransmissionClient(hass, config_entry)
    client_id = config_entry.entry_id
    hass.data[DOMAIN][client_id] = client
    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass, entry):
    """Unload Transmission Entry from config_entry."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
    if hass.data[DOMAIN][entry.entry_id].unsub_timer:
        hass.data[DOMAIN][entry.entry_id].unsub_timer()

    for component in "sensor", "switch":
        await hass.config_entries.async_forward_entry_unload(entry, component)

    del hass.data[DOMAIN]

    return True


async def get_api(hass, host, port, username=None, password=None):
    """Get Transmission client."""
    try:
        api = await hass.async_add_executor_job(
            transmissionrpc.Client, host, port, username, password
        )
        return api

    except TransmissionError as error:
        if "401: Unauthorized" in str(error):
            _LOGGER.error("Credentials for Transmission client are not valid")
            raise AuthenticationError
        if "111: Connection refused" in str(error):
            _LOGGER.error("Connecting to the Transmission client failed")
            raise CannotConnect

        _LOGGER.error(error)
        raise UnknownError


async def async_populate_options(hass, config_entry):
    """Populate default options for Transmission Client."""
    options = {CONF_SCAN_INTERVAL: config_entry.data["options"][CONF_SCAN_INTERVAL]}

    hass.config_entries.async_update_entry(config_entry, options=options)


class TransmissionClient:
    """Transmission Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config_entry = config_entry
        self.scan_interval = self.config_entry.options[CONF_SCAN_INTERVAL]
        self.tm_data = None
        self.unsub_timer = None

    async def async_setup(self):
        """Set up the Transmission client."""

        config = {
            CONF_HOST: self.config_entry.data[CONF_HOST],
            CONF_PORT: self.config_entry.data[CONF_PORT],
            CONF_USERNAME: self.config_entry.data.get(CONF_USERNAME),
            CONF_PASSWORD: self.config_entry.data.get(CONF_PASSWORD),
        }
        try:
            api = await get_api(self.hass, **config)
        except CannotConnect:
            raise ConfigEntryNotReady
        except (AuthenticationError, UnknownError):
            return False

        self.tm_data = self.hass.data[DOMAIN][DATA_TRANSMISSION] = TransmissionData(
            self.hass, self.config_entry, api
        )

        await self.hass.async_add_executor_job(self.tm_data.init_torrent_list)
        await self.hass.async_add_executor_job(self.tm_data.update)
        self.set_scan_interval(self.scan_interval)

        for platform in ["sensor", "switch"]:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )

        def add_torrent(service):
            """Add new torrent to download."""
            torrent = service.data[ATTR_TORRENT]
            if torrent.startswith(
                ("http", "ftp:", "magnet:")
            ) or self.hass.config.is_allowed_path(torrent):
                api.add_torrent(torrent)
            else:
                _LOGGER.warning(
                    "Could not add torrent: unsupported type or no permission"
                )

        self.hass.services.async_register(
            DOMAIN, SERVICE_ADD_TORRENT, add_torrent, schema=SERVICE_ADD_TORRENT_SCHEMA
        )

        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    def set_scan_interval(self, scan_interval):
        """Update scan interval."""

        def refresh(event_time):
            """Get the latest data from Transmission."""
            self.tm_data.update()

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


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(self, hass, config, api):
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.data = None
        self.torrents = None
        self.session = None
        self.available = True
        self._api = api
        self.completed_torrents = []
        self.started_torrents = []

    def update(self):
        """Get the latest data from Transmission instance."""
        try:
            self.data = self._api.session_stats()
            self.torrents = self._api.get_torrents()
            self.session = self._api.get_session()

            self.check_completed_torrent()
            self.check_started_torrent()
            _LOGGER.debug("Torrent Data Updated")

            self.available = True
        except TransmissionError:
            self.available = False
            _LOGGER.error("Unable to connect to Transmission client")

        dispatcher_send(self.hass, DATA_UPDATED)

    def init_torrent_list(self):
        """Initialize torrent lists."""
        self.torrents = self._api.get_torrents()
        self.completed_torrents = [
            x.name for x in self.torrents if x.status == "seeding"
        ]
        self.started_torrents = [
            x.name for x in self.torrents if x.status == "downloading"
        ]

    def check_completed_torrent(self):
        """Get completed torrent functionality."""
        actual_torrents = self.torrents
        actual_completed_torrents = [
            var.name for var in actual_torrents if var.status == "seeding"
        ]

        tmp_completed_torrents = list(
            set(actual_completed_torrents).difference(self.completed_torrents)
        )

        for var in tmp_completed_torrents:
            self.hass.bus.fire("transmission_downloaded_torrent", {"name": var})

        self.completed_torrents = actual_completed_torrents

    def check_started_torrent(self):
        """Get started torrent functionality."""
        actual_torrents = self.torrents
        actual_started_torrents = [
            var.name for var in actual_torrents if var.status == "downloading"
        ]

        tmp_started_torrents = list(
            set(actual_started_torrents).difference(self.started_torrents)
        )

        for var in tmp_started_torrents:
            self.hass.bus.fire("transmission_started_torrent", {"name": var})
        self.started_torrents = actual_started_torrents

    def get_started_torrent_count(self):
        """Get the number of started torrents."""
        return len(self.started_torrents)

    def get_completed_torrent_count(self):
        """Get the number of completed torrents."""
        return len(self.completed_torrents)

    def start_torrents(self):
        """Start all torrents."""
        self._api.start_all()

    def stop_torrents(self):
        """Stop all active torrents."""
        torrent_ids = [torrent.id for torrent in self.torrents]
        self._api.stop_torrent(torrent_ids)

    def set_alt_speed_enabled(self, is_enabled):
        """Set the alternative speed flag."""
        self._api.set_session(alt_speed_enabled=is_enabled)

    def get_alt_speed_enabled(self):
        """Get the alternative speed flag."""
        if self.session is None:
            return None

        return self.session.alt_speed_enabled
