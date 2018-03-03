"""
Sensor for monitoring the contents of a folder.

For more details about this platform, refer to the documentation at
https://home-assistant.io/components/sensor.folder/
"""
import datetime
from datetime import timedelta
import glob
import logging
import os

import voluptuous as vol

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_FOLDER_PATH = 'folder'
CONF_FILTER = 'filter'
CONF_RECURSIVE = 'recursive'
DEFAULT_FILTER = '*'
DEFAULT_NAME = ''
DEFAULT_RECURSIVE = False
FILE = 'file'
SIGNAL_FILE_ADDED = 'file_added'
SIGNAL_FILE_DELETED = 'file_deleted'
SIGNAL_FILE_MODIFIED = 'file_modified'

SCAN_INTERVAL = timedelta(seconds=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FOLDER_PATH): cv.isdir,
    vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_RECURSIVE, default=DEFAULT_RECURSIVE): cv.boolean,
})


def get_timestamp(file_path):
    """Return the timestamp of file."""
    mtime = os.stat(file_path).st_mtime
    return datetime.datetime.fromtimestamp(mtime).isoformat()


def get_files_dict(folder_path, filter_term, recursive):
    """Return the dict of file paths and mod times, applying filter."""
    if recursive:
        query = folder_path + '**/' + filter_term
        files_list = glob.glob(query, recursive=True)
    else:
        query = folder_path + filter_term
        files_list = glob.glob(query, recursive=False)
    files_list = [f for f in files_list if os.path.isfile(f)]
    files_dict = {f: get_timestamp(f) for f in files_list}
    return files_dict


def get_size(files_list):
    """Return the sum of the size in bytes of files in the list."""
    size_list = [os.stat(f).st_size for f in files_list]
    return sum(size_list)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the folder sensor."""
    folder_path = config.get(CONF_FOLDER_PATH)

    if not hass.config.is_allowed_path(folder_path):
        _LOGGER.error("folder %s is not valid or allowed", folder_path)
    else:
        folder = Folder(
            folder_path,
            config.get(CONF_FILTER),
            config.get(CONF_NAME),
            config.get(CONF_RECURSIVE))
        add_devices([folder], True)


class Folder(Entity):
    """Representation of a folder."""

    ICON = 'mdi:folder'

    def __init__(self, folder_path, filter_term, name, recursive):
        """Initialize the data object."""
        folder_path = os.path.join(folder_path, '')  # If no trailing / add it
        self._folder_path = folder_path   # Need to check its a valid path
        self._filter_term = filter_term
        if name == DEFAULT_NAME:
            self._name = os.path.split(os.path.split(folder_path)[0])[1]
        else:
            self._name = name
        self._recursive = recursive
        self._files_record = get_files_dict(
            folder_path, filter_term, recursive)
        self._number_of_files = len(self._files_record)
        self._size = get_size(list(self._files_record.keys()))
        self._unit_of_measurement = 'MB'

    def update(self):
        """Update the sensor."""
        current_files = get_files_dict(
            self._folder_path, self._filter_term, self._recursive)
        self._number_of_files = len(current_files)
        self._size = get_size(list(current_files.keys()))

        for file_path in set(
                             list(current_files.keys()) +
                             list(self._files_record.keys())):

            if file_path not in self._files_record:
                self.hass.bus.fire(
                    SIGNAL_FILE_ADDED, {FILE: file_path})
                self._files_record[file_path] = current_files[file_path]

            elif file_path not in current_files:
                self.hass.bus.fire(
                    SIGNAL_FILE_DELETED, {FILE: file_path})
                self._files_record.pop(file_path, None)

            elif file_path in self._files_record and current_files:
                if self._files_record[file_path] != current_files[file_path]:
                    self.hass.bus.fire(
                        SIGNAL_FILE_MODIFIED, {FILE: file_path})
                    self._files_record[file_path] = current_files[file_path]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        decimals = 2
        size_mb = round(self._size/1e6, decimals)
        return size_mb

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attr = {
            CONF_FOLDER_PATH: self._folder_path,
            CONF_FILTER: self._filter_term,
            CONF_RECURSIVE: self._recursive,
            'number_of_files': self._number_of_files,
            'bytes': self._size,
            }
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
