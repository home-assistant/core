"""Support for monitoring the rtorrent BitTorrent client API."""
from __future__ import annotations

import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_URL,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

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
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS,
        name="Status",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_ALL_TORRENTS,
        name="All Torrents",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_STOPPED_TORRENTS,
        name="Stopped Torrents",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_COMPLETE_TORRENTS,
        name="Complete Torrents",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOADING_TORRENTS,
        name="Uploading Torrents",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOADING_TORRENTS,
        name="Downloading Torrents",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_ACTIVE_TORRENTS,
        name="Active Torrents",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the rtorrent sensors."""
    url = config[CONF_URL]
    name = config[CONF_NAME]

    try:
        rtorrent = xmlrpc.client.ServerProxy(url)
    except (xmlrpc.client.ProtocolError, ConnectionRefusedError) as ex:
        _LOGGER.error("Connection to rtorrent daemon failed")
        raise PlatformNotReady from ex
    monitored_variables = config[CONF_MONITORED_VARIABLES]
    entities = [
        RTorrentSensor(rtorrent, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_variables
    ]

    add_entities(entities)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class RTorrentSensor(SensorEntity):
    """Representation of an rtorrent sensor."""

    def __init__(
        self, rtorrent_client, client_name, description: SensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.client = rtorrent_client
        self.data = None

        self._attr_name = f"{client_name} {description.name}"
        self._attr_available = False

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
            self._attr_available = True
        except (xmlrpc.client.ProtocolError, OSError) as ex:
            _LOGGER.error("Connection to rtorrent failed (%s)", ex)
            self._attr_available = False
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

        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TYPE_CURRENT_STATUS:
            if self.data:
                if upload > 0 and download > 0:
                    self._attr_native_value = "up_down"
                elif upload > 0 and download == 0:
                    self._attr_native_value = "seeding"
                elif upload == 0 and download > 0:
                    self._attr_native_value = "downloading"
                else:
                    self._attr_native_value = STATE_IDLE
            else:
                self._attr_native_value = None

        if self.data:
            if sensor_type == SENSOR_TYPE_DOWNLOAD_SPEED:
                self._attr_native_value = format_speed(download)
            elif sensor_type == SENSOR_TYPE_UPLOAD_SPEED:
                self._attr_native_value = format_speed(upload)
            elif sensor_type == SENSOR_TYPE_ALL_TORRENTS:
                self._attr_native_value = len(all_torrents)
            elif sensor_type == SENSOR_TYPE_STOPPED_TORRENTS:
                self._attr_native_value = len(stopped_torrents)
            elif sensor_type == SENSOR_TYPE_COMPLETE_TORRENTS:
                self._attr_native_value = len(complete_torrents)
            elif sensor_type == SENSOR_TYPE_UPLOADING_TORRENTS:
                self._attr_native_value = uploading_torrents
            elif sensor_type == SENSOR_TYPE_DOWNLOADING_TORRENTS:
                self._attr_native_value = downloading_torrents
            elif sensor_type == SENSOR_TYPE_ACTIVE_TORRENTS:
                self._attr_native_value = active_torrents
