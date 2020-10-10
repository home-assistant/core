"""Sensor for monitoring the contents of a folder."""
from datetime import timedelta
import glob
import logging
import os

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import DATA_MEGABYTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_FOLDER_PATHS = "folder"
CONF_FILTER = "filter"
DEFAULT_FILTER = "*"

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FOLDER_PATHS): cv.isdir,
        vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
    }
)


def get_files_list(folder_path, filter_term):
    """Return the list of files, applying filter."""
    query = folder_path + filter_term
    files_list = glob.glob(query)
    return files_list


def get_size(files_list):
    """Return the sum of the size in bytes of files in the list."""
    size_list = [os.stat(f).st_size for f in files_list if os.path.isfile(f)]
    return sum(size_list)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the folder sensor."""
    path = config.get(CONF_FOLDER_PATHS)

    if not hass.config.is_allowed_path(path):
        _LOGGER.error("folder %s is not valid or allowed", path)
    else:
        folder = Folder(path, config.get(CONF_FILTER))
        add_entities([folder], True)


class Folder(Entity):
    """Representation of a folder."""

    ICON = "mdi:folder"

    def __init__(self, folder_path, filter_term):
        """Initialize the data object."""
        folder_path = os.path.join(folder_path, "")  # If no trailing / add it
        self._folder_path = folder_path  # Need to check its a valid path
        self._filter_term = filter_term
        self._number_of_files = None
        self._size = None
        self._name = os.path.split(os.path.split(folder_path)[0])[1]
        self._unit_of_measurement = DATA_MEGABYTES
        self._file_list = None

    def update(self):
        """Update the sensor."""
        files_list = get_files_list(self._folder_path, self._filter_term)
        self._file_list = files_list
        self._number_of_files = len(files_list)
        self._size = get_size(files_list)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        decimals = 2
        size_mb = round(self._size / 1e6, decimals)
        return size_mb

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        return {
            "path": self._folder_path,
            "filter": self._filter_term,
            "number_of_files": self._number_of_files,
            "bytes": self._size,
            "file_list": self._file_list,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
