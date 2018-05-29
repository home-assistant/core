"""
Support for monitoring the Transmission BitTorrent client API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.transmission/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_MONITORED_VARIABLES, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME, STATE_IDLE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.exceptions import PlatformNotReady

REQUIREMENTS = ['transmissionrpc==0.11']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Transmission'
DEFAULT_PORT = 9091

SENSOR_TYPES = {
    'active_torrents': ['Active Torrents', None],
    'current_status': ['Status', None],
    'download_speed': ['Down Speed', 'MB/s'],
    'paused_torrents': ['Paused Torrents', None],
    'total_torrents': ['Total Torrents', None],
    'upload_speed': ['Up Speed', 'MB/s'],
}

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['torrents']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Transmission sensors."""
    import transmissionrpc
    from transmissionrpc.error import TransmissionError

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)

    try:
        transmission = transmissionrpc.Client(
            host, port=port, user=username, password=password)
        transmission_api = TransmissionData(transmission)
    except TransmissionError as error:
        if str(error).find("401: Unauthorized"):
            _LOGGER.error("Credentials for Transmission client are not valid")
            return

        _LOGGER.warning(
            "Unable to connect to Transmission client: %s:%s", host, port)
        raise PlatformNotReady

    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(TransmissionSensor(variable, transmission_api, name))

    add_devices(dev, True)


class TransmissionSensor(Entity):
    """Representation of a Transmission sensor."""

    def __init__(self, sensor_type, transmission_api, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self._state = None
        self._transmission_api = transmission_api
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._data = None
        self.client_name = client_name
        self.type = sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._transmission_api.available

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        self._transmission_api.update()
        self._data = self._transmission_api.data

        if self.type == 'current_status':
            if self._data:
                upload = self._data.uploadSpeed
                download = self._data.downloadSpeed
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

        if self._data:
            if self.type == 'download_speed':
                mb_spd = float(self._data.downloadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'upload_speed':
                mb_spd = float(self._data.uploadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'active_torrents':
                self._state = self._data.activeTorrentCount
            elif self.type == 'paused_torrents':
                self._state = self._data.pausedTorrentCount
            elif self.type == 'total_torrents':
                self._state = self._data.torrentCount


class TransmissionData(object):
    """Get the latest data and update the states."""

    def __init__(self, api):
        """Initialize the Transmission data object."""
        self.data = None
        self.available = True
        self._api = api

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Transmission instance."""
        from transmissionrpc.error import TransmissionError

        try:
            self.data = self._api.session_stats()
            self.available = True
        except TransmissionError:
            self.available = False
            _LOGGER.error("Unable to connect to Transmission client")
