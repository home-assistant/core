"""Support for monitoring the qBittorrent API."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME, STATE_IDLE)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady

REQUIREMENTS = ['python-qbittorrent==0.3.1']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = 'current_status'
SENSOR_TYPE_DOWNLOAD_SPEED = 'download_speed'
SENSOR_TYPE_UPLOAD_SPEED = 'upload_speed'

DEFAULT_NAME = 'qBittorrent'

SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT_STATUS: ['Status', None],
    SENSOR_TYPE_DOWNLOAD_SPEED: ['Down Speed', 'kB/s'],
    SENSOR_TYPE_UPLOAD_SPEED: ['Up Speed', 'kB/s'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the qbittorrent sensors."""
    from qbittorrent import Client

    name = config.get(CONF_NAME)

    try:
        qbittorrent = Client(config.get(CONF_URL))
        qbittorrent.login(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Connection to qBittorrent failed. Check config.")
        raise PlatformNotReady

    dev = []
    for sensor_type in SENSOR_TYPES:
        sensor = QBittorrentSensor(sensor_type, qbittorrent, name)
        dev.append(sensor)
        sensor.update()

    add_entities(dev)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(Entity):
    """Representation of an qbittorrent sensor."""

    def __init__(self, sensor_type, qbittorrent_client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = qbittorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

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
        """Get the latest data from qbittorrent and updates the state."""
        try:
            data = self.client.sync()
            self._available = True
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Connection to qBittorrent lost. Check config.")
            self._available = False
            return

        download = data['server_state']['dl_info_speed']
        upload = data['server_state']['up_info_speed']

        if self.type == SENSOR_TYPE_CURRENT_STATUS:
            if data:
                if upload > 0 and download > 0:
                    self._state = 'Up/Down'
                elif upload > 0 and download == 0:
                    self._state = 'Seeding'
                elif upload == 0 and download > 0:
                    self._state = 'Downloading'
                else:
                    self._state = STATE_IDLE
            else:
                self._state = None

        if data:
            if self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
                self._state = format_speed(download)
            elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
                self._state = format_speed(upload)
