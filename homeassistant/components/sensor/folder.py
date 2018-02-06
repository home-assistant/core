"""
Sensor for monitoring the contents of a folder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.folder/
"""
from datetime import datetime as dt
from datetime import timedelta
import glob
import logging
import os
import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.template import DATE_STR_FORMAT
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)


CONF_FOLDER_PATHS = 'folder'
CONF_FILTER = 'filter'
DEFAULT_FILTER = '*'

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FOLDER_PATHS): cv.isdir,
    vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the folder sensor."""
    folder = Folder(config.get(CONF_FOLDER_PATHS), config.get(CONF_FILTER))
    add_devices([folder], True)


class Folder(Entity):
    """Representation of a folder."""

    ICON = 'mdi:folder'

    def __init__(self, folder_path, filter_term):
        """Initialize the data object."""
        folder_path = os.path.join(folder_path, '')  # If no trailing / add it
        self._folder_path = folder_path   # Need to check its a valid path
        self._filter_term = filter_term
        self._sorted_files_list = []
        self._number_of_files = None
        self._recent_modified_file = ''
        self._last_updated = ''
        self._name = folder_path.split("/")[-2]
        self._unit_of_measurement = ''
        self.update()

    def update(self):
        """Update the sensor."""
        self._sorted_files_list = self.get_sorted_files_list(
            self._folder_path, self._filter_term)

        self._recent_modified_file = self._sorted_files_list[-1]

        self._last_updated = self.get_last_updated(
            self._recent_modified_file)
        return

    def get_sorted_files_list(self, folder_path, filter_term):
        """Rerturn the sorted list of files in a directory, applying filter.
        List entired sorted by modified time, with most recent first."""
        query = folder_path + filter_term
        files_list = glob.glob(query)
        sorted_files_list = sorted(files_list, key=os.path.getmtime)
        return sorted_files_list

    def get_last_updated(self, recent_modified_file):
        """Rerturn the datetime a file was last modified."""
        modified_time = os.path.getmtime(recent_modified_file)
        modified_time_datetime = dt.fromtimestamp(modified_time)
        return modified_time_datetime.strftime(DATE_STR_FORMAT)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._last_updated

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}
        attrs['folder'] = self._folder_path
        attrs['filter'] = self._filter_term
        attrs['modified_file'] = self._recent_modified_file.split('/')[-1]
        attrs['number_of_files'] = len(self._sorted_files_list)
        attrs['files'] = [f.split('/')[-1] for f in self._sorted_files_list]
        return attrs

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
