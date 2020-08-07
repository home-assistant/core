"""Support for monitoring the rtorrent BitTorrent client API."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DATA_RTORRENT, DATA_UPDATED, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the rtorrent sensors."""
    if discovery_info is None:
        return

    rtorrent_data = hass.data[DATA_RTORRENT]
    name = discovery_info["client_name"]

    devices = []
    for sensor_type in discovery_info["monitored_variables"]:
        devices.append(
            RTorrentSensor(
                rtorrent_data,
                sensor_type,
                name,
                SENSOR_TYPES[sensor_type][0],
                SENSOR_TYPES[sensor_type][1],
                SENSOR_TYPES[sensor_type][2],
            )
        )

    add_entities(devices, True)


def format_speed(speed, unit=2):
    """Return a bytes/s measurement as a human readable string."""
    speed_fmt = float(speed) / (1024 ** unit)
    return round(speed_fmt, 2 if speed_fmt < 0.1 else 1)


class RTorrentSensor(Entity):
    """Representation of an rtorrent sensor."""

    def __init__(
        self,
        rtorrent_data,
        sensor_type,
        client_name,
        sensor_name,
        unit_of_measurement,
        icon,
    ):
        """Initialize the sensor."""
        self._name = f"{client_name} {sensor_name}"
        self.rtorrent_data = rtorrent_data
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._icon = icon

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def available(self):
        """Return true if device is available."""
        return self.rtorrent_data.available

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DATA_UPDATED, self._schedule_immediate_update
            )
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data from rtorrent and updates the state."""
        states = {
            "current_status": self.rtorrent_data.status,
            "upload_speed": format_speed(self.rtorrent_data.upload),
            "download_speed": format_speed(self.rtorrent_data.download),
            "upload_limit": int(format_speed(self.rtorrent_data.upload_limit, 1)),
            "download_limit": int(format_speed(self.rtorrent_data.download_limit, 1)),
            "all_torrents": len(self.rtorrent_data.all_torrents),
            "stopped_torrents": len(self.rtorrent_data.stopped_torrents),
            "complete_torrents": len(self.rtorrent_data.complete_torrents),
            "uploading_torrents": self.rtorrent_data.seeding,
            "downloading_torrents": self.rtorrent_data.downloading,
            "active_torrents": (
                self.rtorrent_data.seeding + self.rtorrent_data.downloading
            ),
        }

        self._state = states.get(self.type, None)
