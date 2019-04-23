"""
Support for monitoring the qBittorrent API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.qbittorrent/
"""
import logging

import voluptuous as vol

from requests.exceptions import RequestException

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


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the qBittorrent sensors."""
    from qbittorrent.client import Client, LoginRequired

    try:
        client = Client(config[CONF_URL])
        client.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady

    name = config.get(CONF_NAME)

    dev = []
    for sensor_type in SENSOR_TYPES:
        sensor = QBittorrentSensor(sensor_type, client, name, LoginRequired)
        dev.append(sensor)

    async_add_entities(dev, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(Entity):
    """Representation of an qBittorrent sensor."""

    def __init__(self, sensor_type, qbittorrent_client,
                 client_name, exception):
        """Initialize the qBittorrent sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = qbittorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = False
        self._exception = exception

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

    async def async_update(self):
        """Get the latest data from qBittorrent and updates the state."""
        try:
            data = self.client.sync()
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

        download = data['server_state']['dl_info_speed']
        upload = data['server_state']['up_info_speed']

        if self.type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                self._state = 'up_down'
            elif upload > 0 and download == 0:
                self._state = 'seeding'
            elif upload == 0 and download > 0:
                self._state = 'downloading'
            else:
                self._state = STATE_IDLE

        elif self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._state = format_speed(download)
        elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
            self._state = format_speed(upload)
