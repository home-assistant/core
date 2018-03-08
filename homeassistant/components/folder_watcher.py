"""
Component for monitoring activity on a folder.
"""
import fnmatch
import os
import logging
import voluptuous as vol
from watchdog.events import FileSystemEventHandler
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['watchdog==0.8.3']
_LOGGER = logging.getLogger(__name__)

CONF_FOLDERS = 'folders'
CONF_FILTER = 'filter'
DEFAULT_FILTER = '*'
DOMAIN = "folder_watcher"
EVENT_TYPE = "event_type"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
        vol.Required(CONF_FOLDERS):
            vol.All(cv.ensure_list, [cv.isdir]),
        })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the folder watcher."""
    conf = config[DOMAIN]
    file_filter = conf[CONF_FILTER]
    paths = conf[CONF_FOLDERS]
    for path in paths:
        if not hass.config.is_allowed_path(path):
            _LOGGER.error("folder %s is not valid or allowed", path)
            return False
        else:
            Watcher(path, file_filter, hass)
    return True


def on_any_event(hass, file_filter, event):
    """On Watcher event, fire HA event."""
    if not event.is_directory:
        file_name = os.path.split(event.src_path)[1]
        if not file_name.startswith('.'):  # Avoid hidden files.
            if fnmatch.fnmatch(file_name, file_filter):  # Apply filter.
                hass.bus.fire(
                    DOMAIN, {
                        EVENT_TYPE: event.event_type,
                        'file': file_name,
                        'folder': os.path.split(event.src_path)[0]})


class Watcher(Entity):
    """Class for starting Watchdog."""
    def __init__(self, path, file_filter, hass):
        from watchdog.observers import Observer
        self._observer = Observer()
        self._observer.schedule(
            WatcherHandler(file_filter, hass),
            path,
            recursive=True)
        self._observer.start()

    def stop_watching(self):
        self._observer.stop()


class WatcherHandler(FileSystemEventHandler):
    """Class for handling Watcher events."""
    def __init__(self, file_filter, hass):
        super().__init__()
        self._file_filter = file_filter
        self.hass = hass

    def process(self, event):
        """Process the Watchdog event."""
        on_any_event(self.hass, self._file_filter, event)

    def on_modified(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

    def on_deleted(self, event):
        self.process(event)
