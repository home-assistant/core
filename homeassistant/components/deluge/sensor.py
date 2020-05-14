"""Support for monitoring the Deluge BitTorrent client API."""
import logging

from deluge_client import DelugeRPCClient, FailedToReconnectException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None

DEFAULT_NAME = "Deluge"
DEFAULT_PORT = 58846
DHT_UPLOAD = 1000
DHT_DOWNLOAD = 1000
SENSOR_TYPES = {
    "current_status": ["Status", None],
    "download_speed": ["Down Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    "upload_speed": ["Up Speed", DATA_RATE_KILOBYTES_PER_SECOND],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Deluge sensors."""

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]

    deluge_api = DelugeRPCClient(host, port, username, password)
    try:
        deluge_api.connect()
    except ConnectionRefusedError:
        _LOGGER.error("Connection to Deluge Daemon failed")
        raise PlatformNotReady
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(DelugeSensor(variable, deluge_api, name))

    add_entities(dev)


class DelugeSensor(Entity):
    """Representation of a Deluge sensor."""

    def __init__(self, sensor_type, deluge_client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = deluge_client
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
        """Get the latest data from Deluge and updates the state."""

        try:
            self.data = self.client.call(
                "core.get_session_status",
                [
                    "upload_rate",
                    "download_rate",
                    "dht_upload_rate",
                    "dht_download_rate",
                ],
            )
            self._available = True
        except FailedToReconnectException:
            _LOGGER.error("Connection to Deluge Daemon Lost")
            self._available = False
            return

        upload = self.data[b"upload_rate"] - self.data[b"dht_upload_rate"]
        download = self.data[b"download_rate"] - self.data[b"dht_download_rate"]

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
