"""Support for monitoring the qBittorrent API."""
from datetime import timedelta
import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"
SENSOR_TYPE_TOTAL_TORRENTS = "total_torrents"
SENSOR_TYPE_ACTIVE_TORRENTS = "active_torrents"
SENSOR_TYPE_INACTIVE_TORRENTS = "inactive_torrents"
SENSOR_TYPE_DOWNLOADING_TORRENTS = "downloading_torrents"
SENSOR_TYPE_SEEDING_TORRENTS = "seeding_torrents"
SENSOR_TYPE_RESUMED_TORRENTS = "resumed_torrents"
SENSOR_TYPE_PAUSED_TORRENTS = "paused_torrents"
SENSOR_TYPE_COMPLETED_TORRENTS = "completed_torrents"

DEFAULT_NAME = "qBittorrent"
TRIM_SIZE = 35

SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT_STATUS: ["Status", None],
    SENSOR_TYPE_DOWNLOAD_SPEED: ["Down Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_UPLOAD_SPEED: ["Up Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_TOTAL_TORRENTS: ["Total Torrents", None],
    SENSOR_TYPE_ACTIVE_TORRENTS: ["Active Torrents", None],
    SENSOR_TYPE_INACTIVE_TORRENTS: ["Inactive Torrents", None],
    SENSOR_TYPE_DOWNLOADING_TORRENTS: ["Downloading", None],
    SENSOR_TYPE_SEEDING_TORRENTS: ["Seeding", None],
    SENSOR_TYPE_RESUMED_TORRENTS: ["Resumed Torrents", None],
    SENSOR_TYPE_PAUSED_TORRENTS: ["Paused Torrents", None],
    SENSOR_TYPE_COMPLETED_TORRENTS: ["Completed Torrents", None],
}

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["torrents"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the qBittorrent sensors."""

    try:
        client = Client(config[CONF_URL])
        client.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException:
        _LOGGER.warning("Unable to connect to Qbittorrent client")
        raise PlatformNotReady

    name = config.get(CONF_NAME)

    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensor = QBittorrentSensor(variable, client, name, LoginRequired)
        dev.append(sensor)

    add_entities(dev, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(Entity):
    """Representation of an qBittorrent sensor."""

    def __init__(self, sensor_type, qbittorrent_client, client_name, exception):
        """Initialize the qBittorrent sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = qbittorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = False
        self._exception = exception
        self._attribute = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attribute

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from qBittorrent and updates the state."""

        try:
            data = self.client.sync_main_data()
            self._available = True
        except RequestException:
            _LOGGER.error("Connection lost")
            self._available = False
            return
        except self._exception:
            _LOGGER.error("Invalid authentication")
            return

        if data is None:
            return

        attributes = {}
        download = data["server_state"]["dl_info_speed"]
        upload = data["server_state"]["up_info_speed"]
        if self.type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                self._state = "up_down"
            elif upload > 0 and download == 0:
                self._state = "seeding"
            elif upload == 0 and download > 0:
                self._state = "downloading"
            else:
                self._state = STATE_IDLE

        elif self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._state = format_speed(download)
        elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
            self._state = format_speed(upload)

        elif self.type == "total_torrents":
            data = self.client.torrents()

            for torrent in data:
                attributes[trim_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "active_torrents":
            data = self.client.torrents(filter="active")

            for torrent in data:
                attributes[trim_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "inactive_torrents":
            data = self.client.torrents(filter="inactive")

            for torrent in data:
                attributes[trim_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "downloading_torrents":
            data = self.client.torrents(filter="downloading")

            for torrent in data:
                attributes[trim_name(torrent)] = format_progress(torrent)

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "seeding_torrents":
            data = self.client.torrents(filter="seeding")

            for torrent in data:
                ratio = torrent["ratio"]
                ratio = float(ratio)
                ratio = f"{ratio:.2f}"

                attributes[trim_name(torrent)] = ratio

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "resumed_torrents":
            data = self.client.torrents(filter="resumed")

            for torrent in data:
                attributes[trim_name(torrent)] = format_progress(torrent)

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "paused_torrents":
            data = self.client.torrents(filter="paused")

            for torrent in data:
                attributes[trim_name(torrent)] = format_progress(torrent)

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "completed_torrents":
            data = self.client.torrents(filter="completed")

            for torrent in data:
                attributes[trim_name(torrent)] = "100.0%"

            self._state = len(data)
            self._attribute = attributes
        elif self.type == "download_speed":
            dlspeed = self.client.global_transfer_info["dl_info_speed"]
            mb_spd = float(dlspeed)
            mb_spd = mb_spd / 1024
            self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
        elif self.type == "upload_speed":
            upspeed = self.client.global_transfer_info["up_info_speed"]
            mb_spd = float(upspeed)
            mb_spd = mb_spd / 1024
            self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)


def trim_name(torrent, trim_size=TRIM_SIZE):
    """Do not show the complete name of the torrent, trim it a bit."""
    name = torrent["name"]

    if len(name) > trim_size:
        name = name[0:trim_size] + "..."

    return name


def format_progress(torrent):
    """Format the progress as a percentage, not as a pointer."""
    progress = torrent["progress"]
    progress = float(progress) * 100
    progress = f"{progress:.1f}%"

    return progress
