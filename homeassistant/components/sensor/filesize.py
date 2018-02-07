"""
Sensor for monitoring the size of a file.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.filesize/
"""
import datetime
import logging
import os

import voluptuous as vol

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)


CONF_FILE_PATHS = 'file_paths'
ICON = 'mdi:file'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FILE_PATHS):
        vol.All(cv.ensure_list, [cv.isfile]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the file size sensor."""
    sensors = []
    for path in config.get(CONF_FILE_PATHS):
        sensors.append(Filesize(path))

    add_devices(sensors, True)


class Filesize(Entity):
    """Encapsulates file size information."""

    def __init__(self, path):
        """Initialize the data object."""
        self._path = path   # Need to check its a valid path
        self._size = None
        self._last_updated = None
        self._name = path.split("/")[-1]
        self._unit_of_measurement = 'MB'

    def update(self):
        """Get the size of the file."""
        self._size = self.get_file_size(self._path)
        self._last_updated = self.get_last_updated(self._path)

    def get_file_size(self, path):
        """Return the size of the file in MB."""
        statinfo = os.stat(path)
        decimals = 2
        file_size = round(statinfo.st_size/1e6, decimals)
        return file_size

    def get_last_updated(self, path):
        """Return the time the file was last modified."""
        statinfo = os.stat(path)
        last_updated = datetime.datetime.fromtimestamp(statinfo.st_mtime)
        last_updated = last_updated.isoformat(' ')
        return last_updated

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._size

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}
        attrs['path'] = self._path
        attrs['last_updated'] = self._last_updated
        return attrs

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
