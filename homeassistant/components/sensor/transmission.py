"""
Support for monitoring the Transmission BitTorrent client API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.transmission/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_NAME, CONF_PORT,
    CONF_MONITORED_VARIABLES, STATE_IDLE)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['transmissionrpc==0.11']

_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None

DEFAULT_NAME = 'Transmission'
DEFAULT_PORT = 9091

SENSOR_TYPES = {
    'active_torrents': ['Active Torrents', None],
    'current_status': ['Status', None],
    'download_speed': ['Down Speed', 'MB/s'],
    'upload_speed': ['Up Speed', 'MB/s'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Transmission sensors."""
    import transmissionrpc
    from transmissionrpc.error import TransmissionError

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)

    transmission_api = transmissionrpc.Client(
        host, port=port, user=username, password=password)
    try:
        transmission_api.session_stats()
    except TransmissionError:
        _LOGGER.exception("Connection to Transmission API failed")
        return False

    # pylint: disable=global-statement
    global _THROTTLED_REFRESH
    _THROTTLED_REFRESH = Throttle(timedelta(seconds=1))(
        transmission_api.session_stats)

    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(TransmissionSensor(variable, transmission_api, name))

    add_devices(dev)


class TransmissionSensor(Entity):
    """Representation of a Transmission sensor."""

    def __init__(self, sensor_type, transmission_client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.tm_client = transmission_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

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

    # pylint: disable=no-self-use
    def refresh_transmission_data(self):
        """Call the throttled Transmission refresh method."""
        from transmissionrpc.error import TransmissionError

        if _THROTTLED_REFRESH is not None:
            try:
                _THROTTLED_REFRESH()
            except TransmissionError:
                _LOGGER.error("Connection to Transmission API failed")

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        self.refresh_transmission_data()

        if self.type == 'current_status':
            if self.tm_client.session:
                upload = self.tm_client.session.uploadSpeed
                download = self.tm_client.session.downloadSpeed
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

        if self.tm_client.session:
            if self.type == 'download_speed':
                mb_spd = float(self.tm_client.session.downloadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'upload_speed':
                mb_spd = float(self.tm_client.session.uploadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'active_torrents':
                self._state = self.tm_client.session.activeTorrentCount
