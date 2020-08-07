"""The rtorrent component."""
from datetime import timedelta
import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_RATE_MEGABYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

ATTR_SPEED = "speed"

DOMAIN = "rtorrent"
DATA_RTORRENT = "data_rtorrent"
DATA_UPDATED = "rtorrent_data_updated"

DEFAULT_NAME = "rTorrent"
DEFAULT_SPEED_LIMIT = 1000  # 1 MB/s

DEFAULT_SCAN_INTERVAL = timedelta(seconds=5)

SENSOR_TYPES = {
    "current_status": ["Status", None, "mdi:server-network"],
    "upload_speed": ["Up Speed", DATA_RATE_MEGABYTES_PER_SECOND, "mdi:upload"],
    "download_speed": ["Down Speed", DATA_RATE_MEGABYTES_PER_SECOND, "mdi:download"],
    "upload_limit": ["Up Limit", DATA_RATE_KILOBYTES_PER_SECOND, "mdi:upload"],
    "download_limit": ["Down Limit", DATA_RATE_KILOBYTES_PER_SECOND, "mdi:download"],
    "all_torrents": ["All Torrents", None, "mdi:view-list-outline"],
    "stopped_torrents": ["Stopped Torrents", None, "mdi:stop"],
    "complete_torrents": ["Complete Torrents", None, "mdi:playlist_check"],
    "uploading_torrents": ["Uploading Torrents", None, "mdi:upload-multiple"],
    "downloading_torrents": ["Downloading Torrents", None, "mdi:download-multiple"],
    "active_torrents": ["Active Torrents", None, "mdi:playlist-play"],
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(
                    CONF_MONITORED_VARIABLES, default=list(SENSOR_TYPES)
                ): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_DOWNLOAD_SPEED = "set_download_speed"
SERVICE_SET_UPLOAD_SPEED = "set_upload_speed"
SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.positive_int}
)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    url = config[DOMAIN][CONF_URL]
    name = config[DOMAIN][CONF_NAME]
    scan_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    try:
        rtorrent = xmlrpc.client.ServerProxy(url)
    except (xmlrpc.client.ProtocolError, ConnectionRefusedError) as ex:
        _LOGGER.error("Connection to rtorrent daemon failed")
        raise PlatformNotReady from ex

    rtorrent_data = hass.data[DATA_RTORRENT] = RTorrentData(hass, rtorrent)
    rtorrent_data.update()

    def service_handler(call):
        """Handle service calls."""
        if call.service == SERVICE_SET_DOWNLOAD_SPEED:
            limit = call.data.get(ATTR_SPEED, DEFAULT_SPEED_LIMIT)
            rtorrent.set_download_rate(f"{limit}k")
        elif call.service == SERVICE_SET_UPLOAD_SPEED:
            limit = call.data.get(ATTR_SPEED, DEFAULT_SPEED_LIMIT)
            rtorrent.set_upload_rate(f"{limit}k")

    hass.services.register(
        DOMAIN, SERVICE_SET_DOWNLOAD_SPEED, service_handler, schema=SPEED_LIMIT_SCHEMA
    )

    hass.services.register(
        DOMAIN, SERVICE_SET_UPLOAD_SPEED, service_handler, schema=SPEED_LIMIT_SCHEMA
    )

    def refresh(event_time):
        """Get the latest data from rTorrent."""
        rtorrent_data.update()

    track_time_interval(hass, refresh, scan_interval)

    sensorconfig = {
        "client_name": name,
        "monitored_variables": config[DOMAIN][CONF_MONITORED_VARIABLES],
    }

    hass.helpers.discovery.load_platform("sensor", DOMAIN, sensorconfig, config)

    # Return boolean to indicate that initialization was successfully.
    return True


class RTorrentData:
    """Get the latest data and update the states."""

    def __init__(self, hass, api):
        """Initialize the rTorrent XMLRPC API."""
        self.hass = hass
        self.available = True
        self._api = api
        self.data = None
        self.upload = None
        self.download = None
        self.upload_limit = None
        self.download_limit = None
        self.all_torrents = None
        self.stopped_torrents = None
        self.complete_torrents = None
        self.seeding = None
        self.downloading = None
        self.status = None

    def update(self):
        """Get the latest data from rTorrent instance."""
        multicall = xmlrpc.client.MultiCall(self._api)
        multicall.throttle.global_up.rate()
        multicall.throttle.global_down.rate()
        multicall.throttle.global_up.max_rate()
        multicall.throttle.global_down.max_rate()
        multicall.d.multicall2("", "main")
        multicall.d.multicall2("", "stopped")
        multicall.d.multicall2("", "complete")
        multicall.d.multicall2("", "seeding", "d.up.rate=")
        multicall.d.multicall2("", "leeching", "d.down.rate=")

        try:
            self.data = multicall()
            self.available = True
            dispatcher_send(self.hass, DATA_UPDATED)
        except (xmlrpc.client.ProtocolError, ConnectionRefusedError, OSError) as err:
            self.available = False
            _LOGGER.error("Unable to refresh rTorrent data: %s", err)
            return
        self.upload = self.data[0]
        self.download = self.data[1]
        self.upload_limit = self.data[2]
        self.download_limit = self.data[3]
        self.all_torrents = self.data[4]
        self.stopped_torrents = self.data[5]
        self.complete_torrents = self.data[6]
        self.seeding = len([t for t in self.data[7] if t[0]])
        self.downloading = len([t for t in self.data[8] if t[0]])
        if self.seeding > 0:
            if self.downloading > 0:
                self.status = "up_down"
            else:
                self.status = "seeding"
        else:
            if self.downloading > 0:
                self.status = "downloading"
            else:
                self.status = STATE_IDLE
