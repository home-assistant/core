"""Support for monitoring the qBittorrent API."""
import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
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
DEFAULT_CONDITIONS = ["current_status", "download_speed", "upload_speed"]
TRIM_SIZE = 35

SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT_STATUS: ["Status", None],
    SENSOR_TYPE_DOWNLOAD_SPEED: ["Down Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_UPLOAD_SPEED: ["Up Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_TOTAL_TORRENTS: ["Total Torrents", None],
    SENSOR_TYPE_ACTIVE_TORRENTS: ["Active Torrents", None],
    SENSOR_TYPE_INACTIVE_TORRENTS: ["Inactive Torrents", None],
    SENSOR_TYPE_DOWNLOADING_TORRENTS: ["Downloading Torrents", None],
    SENSOR_TYPE_SEEDING_TORRENTS: ["Seeding Torrents", None],
    SENSOR_TYPE_RESUMED_TORRENTS: ["Resumed Torrents", None],
    SENSOR_TYPE_PAUSED_TORRENTS: ["Paused Torrents", None],
    SENSOR_TYPE_COMPLETED_TORRENTS: ["Completed Torrents", None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_CONDITIONS): vol.All(
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
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err

    name = config.get(CONF_NAME)
    monitored_variables = config.get(CONF_MONITORED_CONDITIONS)

    dev = []
    for monitored_variable in monitored_variables:
        sensor = QBittorrentSensor(monitored_variable, client, name, LoginRequired)
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
        self.attrs = {}
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = False
        self._exception = exception

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
        """Return device specific state attributes."""
        return self.attrs

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
                self.attrs = attributes
            elif upload > 0 and download == 0:
                self._state = "seeding"
                self.attrs = attributes
            elif upload == 0 and download > 0:
                self._state = "downloading"
                self.attrs = attributes
            else:
                self._state = STATE_IDLE
                self.attrs = attributes
        elif self.type == "total_torrents":
            data = self.client.torrents()

            for torrent in data:
                attributes[format_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "active_torrents":
            data = self.client.torrents(filter="active")

            for torrent in data:
                attributes[format_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "inactive_torrents":
            data = self.client.torrents(filter="inactive")

            for torrent in data:
                attributes[format_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "downloading_torrents":
            data = self.client.torrents(filter="downloading")
            for torrent in data:
                attributes[format_name(torrent)] = format_progress(torrent)

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "seeding_torrents":
            data = self.client.torrents(filter="seeding")

            for torrent in data:
                ratio = torrent["ratio"]
                ratio = float(ratio)
                ratio = f"{ratio:.2f}"

                attributes[format_name(torrent)] = ratio

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "resumed_torrents":
            data = self.client.torrents(filter="resumed")

            for torrent in data:
                attributes[format_name(torrent)] = format_progress(torrent)

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "paused_torrents":
            data = self.client.torrents(filter="paused")

            for torrent in data:
                attributes[format_name(torrent)] = format_progress(torrent)

            self._state = len(data)
            self.attrs = attributes
        elif self.type == "completed_torrents":
            data = self.client.torrents(filter="completed")

            for torrent in data:
                attributes[format_name(torrent)] = "100.0%"

            self._state = len(data)
            self.attrs = attributes

        elif self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._state = format_speed(download)
            self.attrs = attributes

        elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
            self._state = format_speed(upload)
            self.attrs = attributes


def format_name(torrent, trim_size=TRIM_SIZE):
    """Return the formatted name of the torrent to fit better within UI."""
    name = torrent["name"]
    if len(name) > trim_size:
        name = name[0:trim_size] + "..."
    return name


def format_progress(torrent):
    """Return the progress percentage of the torrent."""
    progress = torrent["progress"]
    progress = float(progress) * 100
    progress = f"{progress:.1f}%"
    return progress
