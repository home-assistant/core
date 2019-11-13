"""Support for monitoring the Deluge BitTorrent client API."""
import logging

from homeassistant.const import CONF_NAME, STATE_IDLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def setup_platform(hass, config, add_entities, discovery_info=None):
    """Import config from configuration.yaml."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Deluge sensors."""

    client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    dev = []
    for sensor_type in SENSOR_TYPES:
        dev.append(DelugeSensor(sensor_type, client, name,))

    async_add_entities(dev, True)


class DelugeSensor(Entity):
    """Representation of a Deluge sensor."""

    def __init__(self, sensor_type, client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.data = None
        self.unsub_dispatcher = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{self.client.api.host}-{self.name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def available(self):
        """Return true if device is available."""
        return self.client.api.available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, self.client.api.signal_update, self._schedule_immediate_update,
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data from Deluge and updates the state."""
        self.data = self.client.api.data

        if self.type == "completed_torrents":
            self._state = self.client.api.get_completed_torrent_count()
        elif self.type == "started_torrents":
            self._state = self.client.api.get_started_torrent_count()

        if self.data:
            upload = self.data["upload_rate"] - self.data["dht_upload_rate"]
            download = self.data["download_rate"] - self.data["dht_download_rate"]

        if self.type == "current_status":
            if self.data:
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

        if self.data:
            if self.type == "download_speed":
                kb_spd = float(download)
                kb_spd = kb_spd / 1024
                self._state = round(kb_spd, 2 if kb_spd < 0.1 else 1)
            elif self.type == "upload_speed":
                kb_spd = float(upload)
                kb_spd = kb_spd / 1024
                self._state = round(kb_spd, 2 if kb_spd < 0.1 else 1)
            elif self.type == "active_torrents":
                self._state = self.client.api.get_active_torrents_count()
            elif self.type == "paused_torrents":
                self._state = self.client.api.get_paused_torrents_count()
            elif self.type == "total_torrents":
                self._state = self.client.api.get_torrents_count()

    async def will_remove_from_hass(self):
        """Unsub from update dispatcher."""
        if self.unsub_dispatcher:
            self.unsub_dispatcher()
