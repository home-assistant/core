"""Support for monitoring the rtorrent BitTorrent client API."""
import logging
import xmlrpc.client

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_URL, CONF_NAME,
    CONF_MONITORED_VARIABLES, STATE_IDLE)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = 'current_status'
SENSOR_TYPE_DOWNLOAD_SPEED = 'download_speed'
SENSOR_TYPE_UPLOAD_SPEED = 'upload_speed'

DEFAULT_NAME = 'rtorrent'
SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT_STATUS: ['Status', None],
    SENSOR_TYPE_DOWNLOAD_SPEED: ['Down Speed', 'kB/s'],
    SENSOR_TYPE_UPLOAD_SPEED: ['Up Speed', 'kB/s'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the rtorrent sensors."""
    url = config[CONF_URL]
    name = config[CONF_NAME]

    try:
        rtorrent = xmlrpc.client.ServerProxy(url)
    except (xmlrpc.client.ProtocolError, ConnectionRefusedError):
        _LOGGER.error("Connection to rtorrent daemon failed")
        raise PlatformNotReady
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(RTorrentSensor(variable, rtorrent, name))

    add_entities(dev)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class RTorrentSensor(Entity):
    """Representation of an rtorrent sensor."""

    def __init__(self, sensor_type, rtorrent_client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = rtorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.data = None
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
        """Get the latest data from rtorrent and updates the state."""
        multicall = xmlrpc.client.MultiCall(self.client)
        multicall.throttle.global_up.rate()
        multicall.throttle.global_down.rate()

        try:
            self.data = multicall()
            self._available = True
        except (xmlrpc.client.ProtocolError, ConnectionRefusedError):
            _LOGGER.error("Connection to rtorrent lost")
            self._available = False
            return

        upload = self.data[0]
        download = self.data[1]

        if self.type == SENSOR_TYPE_CURRENT_STATUS:
            if self.data:
                if upload > 0 and download > 0:
                    self._state = 'up_down'
                elif upload > 0 and download == 0:
                    self._state = 'seeding'
                elif upload == 0 and download > 0:
                    self._state = 'downloading'
                else:
                    self._state = STATE_IDLE
            else:
                self._state = None

        if self.data:
            if self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
                self._state = format_speed(download)
            elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
                self._state = format_speed(upload)
