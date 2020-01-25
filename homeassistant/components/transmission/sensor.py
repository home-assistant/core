"""Support for monitoring the Transmission BitTorrent client API."""
import logging

from homeassistant.const import CONF_NAME, STATE_IDLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SENSOR_TYPES, STATE_ATTR_TORRENT_INFO

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Transmission sensors."""

    tm_client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    dev = []
    for sensor_type in SENSOR_TYPES:
        dev.append(
            TransmissionSensor(
                sensor_type,
                tm_client,
                name,
                SENSOR_TYPES[sensor_type][0],
                SENSOR_TYPES[sensor_type][1],
            )
        )

    async_add_entities(dev, True)


class TransmissionSensor(Entity):
    """Representation of a Transmission sensor."""

    def __init__(
        self, sensor_type, tm_client, client_name, sensor_name, unit_of_measurement
    ):
        """Initialize the sensor."""
        self._name = sensor_name
        self._state = None
        self._tm_client = tm_client
        self._unit_of_measurement = unit_of_measurement
        self._data = None
        self.client_name = client_name
        self.type = sensor_type
        self.unsub_update = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self._tm_client.api.host}-{self.name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._tm_client.api.available

    @property
    def device_state_attributes(self):
        """Return the state attributes, if any."""
        if self._tm_client.api.started_torrent_dict and self.type == "started_torrents":
            return {STATE_ATTR_TORRENT_INFO: self._tm_client.api.started_torrent_dict}
        return None

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass,
            self._tm_client.api.signal_update,
            self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
            self.unsub_update = None

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        self._data = self._tm_client.api.data

        if self.type == "completed_torrents":
            self._state = self._tm_client.api.get_completed_torrent_count()
        elif self.type == "started_torrents":
            self._state = self._tm_client.api.get_started_torrent_count()

        if self.type == "current_status":
            if self._data:
                upload = self._data.uploadSpeed
                download = self._data.downloadSpeed
                if upload > 0 and download > 0:
                    self._state = "Up/Down"
                elif upload > 0 and download == 0:
                    self._state = "Seeding"
                elif upload == 0 and download > 0:
                    self._state = "Downloading"
                else:
                    self._state = STATE_IDLE
            else:
                self._state = None

        if self._data:
            if self.type == "download_speed":
                mb_spd = float(self._data.downloadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == "upload_speed":
                mb_spd = float(self._data.uploadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == "active_torrents":
                self._state = self._data.activeTorrentCount
            elif self.type == "paused_torrents":
                self._state = self._data.pausedTorrentCount
            elif self.type == "total_torrents":
                self._state = self._data.torrentCount
