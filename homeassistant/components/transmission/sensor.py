"""
Support for monitoring the Transmission BitTorrent client API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.transmission/
"""
from datetime import timedelta

import logging

from homeassistant.components.transmission import (
    DATA_TRANSMISSION, SENSOR_TYPES)
from homeassistant.const import STATE_IDLE
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DEPENDENCIES = ['transmission']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Transmission'

SCAN_INTERVAL = timedelta(seconds=120)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Transmission sensors."""
    if discovery_info is None:
        return

    transmission_api = hass.data[DATA_TRANSMISSION]
    monitored_variables = discovery_info['sensors']
    name = discovery_info['client_name']

    dev = []
    for sensor_type in monitored_variables:
        dev.append(TransmissionSensor(
            sensor_type,
            transmission_api,
            name,
            SENSOR_TYPES[sensor_type][0],
            SENSOR_TYPES[sensor_type][1]))

    add_entities(dev, True)


class TransmissionSensor(Entity):
    """Representation of a Transmission sensor."""

    def __init__(
            self,
            sensor_type,
            transmission_api,
            client_name,
            sensor_name,
            unit_of_measurement):
        """Initialize the sensor."""
        self._name = sensor_name
        self._state = None
        self._transmission_api = transmission_api
        self._unit_of_measurement = unit_of_measurement
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

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Transmission and updates the state."""
        self._transmission_api.update()
        self._data = self._transmission_api.data

        if self.type == 'completed_torrents':
            self._state = self._transmission_api.get_completed_torrent_count()
        elif self.type == 'started_torrents':
            self._state = self._transmission_api.get_started_torrent_count()

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
