"""Support for monitoring the rtorrent BitTorrent client API."""
import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_URL,
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
SENSOR_TYPE_ALL_TORRENTS = "all_torrents"
SENSOR_TYPE_STOPPED_TORRENTS = "stopped_torrents"
SENSOR_TYPE_COMPLETE_TORRENTS = "complete_torrents"
SENSOR_TYPE_UPLOADING_TORRENTS = "uploading_torrents"
SENSOR_TYPE_DOWNLOADING_TORRENTS = "downloading_torrents"
SENSOR_TYPE_ACTIVE_TORRENTS = "active_torrents"

DEFAULT_NAME = "rtorrent"
SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT_STATUS: ["Status", None],
    SENSOR_TYPE_DOWNLOAD_SPEED: ["Down Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_UPLOAD_SPEED: ["Up Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_ALL_TORRENTS: ["All Torrents", None],
    SENSOR_TYPE_STOPPED_TORRENTS: ["Stopped Torrents", None],
    SENSOR_TYPE_COMPLETE_TORRENTS: ["Complete Torrents", None],
    SENSOR_TYPE_UPLOADING_TORRENTS: ["Uploading Torrents", None],
    SENSOR_TYPE_DOWNLOADING_TORRENTS: ["Downloading Torrents", None],
    SENSOR_TYPE_ACTIVE_TORRENTS: ["Active Torrents", None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the rtorrent sensors."""
    url = config[CONF_URL]
    name = config[CONF_NAME]

    try:
        rtorrent = xmlrpc.client.ServerProxy(url)
    except (xmlrpc.client.ProtocolError, ConnectionRefusedError):
        _LOGGER.error("Connection to rtorrent daemon failed")
        raise PlatformNotReady
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(RTorrentSensor(variable, rtorrent, name))

    add_entities(dev)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class RTorrentSensor(Entity):
    """Representation of an rtorrent sensor."""

    def __init__(self, sensor_type, rtorrent_client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = rtorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.data = None
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from rtorrent and updates the state."""
        multicall = xmlrpc.client.MultiCall(self.client)
        multicall.throttle.global_up.rate()
        multicall.throttle.global_down.rate()
        multicall.d.multicall2("", "main")
        multicall.d.multicall2("", "stopped")
        multicall.d.multicall2("", "complete")
        multicall.d.multicall2("", "seeding", "d.up.rate=")
        multicall.d.multicall2("", "leeching", "d.down.rate=")

        try:
            self.data = multicall()
            self._available = True
        except (xmlrpc.client.ProtocolError, ConnectionRefusedError, OSError) as ex:
            _LOGGER.error("Connection to rtorrent failed (%s)", ex)
            self._available = False
            return

        upload = self.data[0]
        download = self.data[1]
        all_torrents = self.data[2]
        stopped_torrents = self.data[3]
        complete_torrents = self.data[4]

        uploading_torrents = 0
        for up_torrent in self.data[5]:
            if up_torrent[0]:
                uploading_torrents += 1

        downloading_torrents = 0
        for down_torrent in self.data[6]:
            if down_torrent[0]:
                downloading_torrents += 1

        active_torrents = uploading_torrents + downloading_torrents

        if self.type == SENSOR_TYPE_CURRENT_STATUS:
            if self.data:
                if upload > 0 and download > 0:
                    self._state = "up_down"
                elif upload > 0 and download == 0:
                    self._state = "seeding"
                elif upload == 0 and download > 0:
                    self._state = "downloading"
                else:
                    self._state = STATE_IDLE
            else:
                self._state = None

        if self.data:
            if self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
                self._state = format_speed(download)
            elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
                self._state = format_speed(upload)
            elif self.type == SENSOR_TYPE_ALL_TORRENTS:
                self._state = len(all_torrents)
            elif self.type == SENSOR_TYPE_STOPPED_TORRENTS:
                self._state = len(stopped_torrents)
            elif self.type == SENSOR_TYPE_COMPLETE_TORRENTS:
                self._state = len(complete_torrents)
            elif self.type == SENSOR_TYPE_UPLOADING_TORRENTS:
                self._state = uploading_torrents
            elif self.type == SENSOR_TYPE_DOWNLOADING_TORRENTS:
                self._state = downloading_torrents
            elif self.type == SENSOR_TYPE_ACTIVE_TORRENTS:
                self._state = active_torrents
