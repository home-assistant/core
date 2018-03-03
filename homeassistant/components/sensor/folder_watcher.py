"""
Sensor for monitoring activity on a folder.
"""
import datetime
from datetime import timedelta
import logging
import os
import voluptuous as vol

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_FOLDER_PATH = 'folder'

SCAN_INTERVAL = timedelta(seconds=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FOLDER_PATH): cv.isdir,
})


def get_timestamp(dir_entry):
    """Return the timestamp of file modification."""
    mtime = dir_entry.stat().st_mtime
    return datetime.datetime.fromtimestamp(mtime).isoformat()


def get_files(path):
    """Return the dict of files and timestamps."""
    files = {}
    with os.scandir(path) as it:
        for entry in it:
            if not entry.name.startswith('.') and entry.is_file():
                files[entry.name] = get_timestamp(entry)
    return files


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the folder watcher."""
    folder_path = config.get(CONF_FOLDER_PATH)
    if not hass.config.is_allowed_path(folder_path):
        _LOGGER.error("folder %s is not valid or allowed", folder_path)
    else:
        folder_watcher = Watcher(folder_path, hass)
        add_devices([folder_watcher], True)


class Watcher(Entity):
    """Class for watching a folder, state recorded in a dict."""

    ICON = 'mdi:folder'

    def __init__(self, folder_path, hass):
        self._folder_path = os.path.join(folder_path, '')  # Ass trailing /
        self._hass = hass
        self._updated = False
        self._files = get_files(self._folder_path)
        self._name = os.path.split(
            os.path.split(self._folder_path)[0])[1] + "_watcher"
        self._state = None

    def update(self):
        """Update the watcher."""
        current_files = []
        previous_files = list(self._files.keys())

        with os.scandir(self._folder_path) as folder:
            for entry in folder:
                if not entry.name.startswith('.') and entry.is_file():
                    mtime = get_timestamp(entry)
                    fname = entry.name
                    current_files.append(fname)  # Keep record of current files

                    # If file not in files list, add the entry
                    if fname not in self._files:
                        self._hass.bus.fire('file_added', {'file': fname})
                        self._state = fname + " added"
                        self._files[fname] = mtime

                    # If exists and modified, update timestamp
                    elif fname in self._files and self._files[fname] != mtime:
                        self._hass.bus.fire('file_modified', {'file': fname})
                        self._state = fname + " modified"
                        self._files[fname] = mtime

            # Check if any files deleted
            for fname in list(set(previous_files) - set(current_files)):
                self._hass.bus.fire('file_deleted', {'file': fname})
                self._state = fname + " deleted"
                self._files.pop(fname, None)  # Delete the entry

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attr = {
            'path': self._folder_path
            }
        return attr
