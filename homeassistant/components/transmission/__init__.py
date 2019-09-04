"""Support for the Transmission BitTorrent client API."""
from datetime import timedelta
import logging

import voluptuous as vol
import transmissionrpc
from transmissionrpc.error import TransmissionError

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from .const import (
    DOMAIN,
    CONF_TURTLE_MODE,
    CONF_SENSOR_TYPES,
    ATTR_TORRENT,
    SERVICE_ADD_TORRENT,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.config_entries import SOURCE_IMPORT

from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DATA_UPDATED = "transmission_data_updated"
DATA_TRANSMISSION = "data_transmission"

DEFAULT_NAME = "Transmission"
DEFAULT_PORT = 9091
DEFAULT_SCAN_INTERVAL = 120

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
                vol.Optional(CONF_TURTLE_MODE, default=False): cv.boolean,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(
                    CONF_MONITORED_CONDITIONS, default=["current_status"]
                ): vol.All(cv.ensure_list, [vol.In(CONF_SENSOR_TYPES)]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Transmission Component from config."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Transmission Component."""
    if not config_entry.options:
        await async_populate_options(hass, config_entry)

    client = TransmissionClient(hass, config_entry)
    if not await client.async_setup():
        return False

    return True


async def async_populate_options(hass, config_entry):
    """Populate default options for Transmission Client."""
    options = {}
    options[CONF_MONITORED_CONDITIONS] = {}
    for sensor in CONF_SENSOR_TYPES:
        options[CONF_MONITORED_CONDITIONS][sensor] = config_entry.data["options"].get(
            sensor, False
        )
    options[CONF_TURTLE_MODE] = config_entry.data["options"].get(
        CONF_TURTLE_MODE, False
    )
    options[CONF_SCAN_INTERVAL] = config_entry.data["options"].get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )

    hass.config_entries.async_update_entry(config_entry, options=options)


async def async_unload_entry(hass, entry):
    """Unload Transmission Entry from config_entry."""
    hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
    return True


class TransmissionClient:
    """Transmission Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Transmission RPC API."""
        self.hass = hass
        self.config_entry = config_entry
        self.host = self.config_entry.data[CONF_HOST]
        self.username = self.config_entry.data.get(CONF_USERNAME)
        self.password = self.config_entry.data.get(CONF_PASSWORD)
        self.port = self.config_entry.data[CONF_PORT]
        self.scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

    async def async_setup(self):
        """Set up the Transmission client."""
        hass = self.hass
        try:
            api = transmissionrpc.Client(
                self.host, port=self.port, user=self.username, password=self.password
            )
            api.session_stats()
        except TransmissionError as error:
            if str(error).find("401: Unauthorized"):
                _LOGGER.error("Credentials for" " Transmission client are not valid")
            return False
        tm_data = self.hass.data[DATA_TRANSMISSION] = TransmissionData(
            self.hass, self.config_entry, api
        )

        tm_data.update()
        await tm_data.async_init_torrent_list()

        def refresh(event_time):
            """Get the latest data from Transmission."""
            tm_data.update()

        async_track_time_interval(
            self.hass, refresh, timedelta(seconds=self.scan_interval)
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(self.config_entry, "sensor")
        )
        if self.config_entry.options.get(CONF_TURTLE_MODE):
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, "switch"
                )
            )

        def add_torrent(self, service):
            """Add new torrent to download."""
            torrent = service.data[ATTR_TORRENT]
            if torrent.startswith(
                ("http", "ftp:", "magnet:")
            ) or self.hass.config.is_allowed_path(torrent):
                self.api.add_torrent(torrent)
            else:
                _LOGGER.warning(
                    "Could not add torrent: " "unsupported type or no permission"
                )

        hass.services.async_register(
            DOMAIN, SERVICE_ADD_TORRENT, add_torrent, schema=SERVICE_ADD_TORRENT_SCHEMA
        )
        return True


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(self, hass, config, api):
        """Initialize the Transmission RPC API."""
        self.data = None
        self.torrents = None
        self.session = None
        self.available = True
        self._api = api
        self.completed_torrents = []
        self.started_torrents = []
        self.hass = hass
        self.scan_interval = timedelta(
            seconds=config.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

    def update(self):
        """Get the latest data from Transmission instance."""
        from transmissionrpc.error import TransmissionError

        try:
            self.data = self._api.session_stats()
            self.torrents = self._api.get_torrents()
            self.session = self._api.get_session()

            self.check_completed_torrent()
            self.check_started_torrent()

            dispatcher_send(self.hass, DATA_UPDATED)

            _LOGGER.debug("Torrent Data updated")
            self.available = True
        except TransmissionError:
            self.available = False
            _LOGGER.error("Unable to connect to Transmission client")

    async def async_init_torrent_list(self):
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

    def set_alt_speed_enabled(self, is_enabled):
        """Set the alternative speed flag."""
        self._api.set_session(alt_speed_enabled=is_enabled)

    def get_alt_speed_enabled(self):
        """Get the alternative speed flag."""
        if self.session is None:
            return None

        return self.session.alt_speed_enabled
