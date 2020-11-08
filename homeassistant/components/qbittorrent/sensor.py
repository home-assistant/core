"""Support for monitoring the qBittorrent API."""

from homeassistant.helpers.dispatcher import async_dispatcher_connect
import logging

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException


from homeassistant.const import (
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.helpers.entity import Entity
from .wrapper_functions import get_main_data_client, retrieve_torrentdata

from .const import (
    DATA_KEY_CLIENT,
    DATA_KEY_NAME,
    SENSOR_TYPE_ACTIVE_TORRENTS,
    SENSOR_TYPE_COMPLETED_TORRENTS,
    SENSOR_TYPE_CURRENT_STATUS,
    SENSOR_TYPE_DOWNLOAD_SPEED,
    SENSOR_TYPE_DOWNLOADING_TORRENTS,
    SENSOR_TYPE_INACTIVE_TORRENTS,
    SENSOR_TYPE_PAUSED_TORRENTS,
    SENSOR_TYPE_RESUMED_TORRENTS,
    SENSOR_TYPE_SEEDING_TORRENTS,
    SENSOR_TYPE_TOTAL_TORRENTS,
    SENSOR_TYPE_UPLOAD_SPEED,
    TRIM_SIZE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the qBittorrent sensor."""

    qbit_data = hass.data[DOMAIN][entry.entry_id]
    name = qbit_data[DATA_KEY_NAME]
    variables = SENSOR_TYPES
    sensors = [
        QBittorrentSensor(
            sensor_name,
            qbit_data[DATA_KEY_CLIENT],
            name,
            LoginRequired,
            entry.entry_id,
        )
        for sensor_name in variables
    ]
    async_add_entities(sensors, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(Entity):
    """Representation of an qBittorrent sensor."""

    def __init__(
        self,
        sensor_type,
        qbittorrent_client,
        client_name,
        exception,
        server_unique_id,
    ):
        """Initialize the qBittorrent sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = qbittorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = False
        self._exception = exception
        self._server_unique_id = server_unique_id
        self._attribute = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._name}"

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

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:cloud-download"

    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "name": self.client_name,
            "manufacturer": "QBittorrent",
        }

    async def async_update(self):
        """Get the latest data from qBittorrent and updates the state."""

        try:
            data = await self.hass.async_add_executor_job(
                get_main_data_client, self.client
            )
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

        elif self.type == SENSOR_TYPE_TOTAL_TORRENTS:
            torrents = data["torrents"]

            for torrent in torrents:
                torrentattr = torrents[torrent]
                attributes[trim_name(torrentattr, TRIM_SIZE - 5)] = torrentattr["state"]

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_ACTIVE_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "active"
            )

            for torrent in torrents:
                attributes[trim_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_INACTIVE_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "inactive"
            )

            for torrent in torrents:
                attributes[trim_name(torrent, TRIM_SIZE - 5)] = torrent["state"]

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_DOWNLOADING_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "downloading"
            )

            for torrent in torrents:
                attributes[trim_name(torrent)] = format_progress(torrent)

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_SEEDING_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "seeding"
            )
            for torrent in torrents:
                ratio = torrent["ratio"]
                ratio = float(ratio)
                ratio = f"{ratio:.2f}"

                attributes[trim_name(torrent)] = ratio

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_RESUMED_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "resumed"
            )

            for torrent in torrents:
                attributes[trim_name(torrent)] = format_progress(torrent)

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_PAUSED_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "paused"
            )

            for torrent in torrents:
                attributes[trim_name(torrent)] = format_progress(torrent)

            self._state = len(torrents)
            self._attribute = attributes
        elif self.type == SENSOR_TYPE_COMPLETED_TORRENTS:
            torrents = await self.hass.async_add_executor_job(
                retrieve_torrentdata, self.client, "completed"
            )

            for torrent in torrents:
                attributes[trim_name(torrent)] = "100.0%"

            self._state = len(torrents)
            self._attribute = attributes


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
