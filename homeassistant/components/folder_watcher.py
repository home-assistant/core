"""
Component for monitoring activity on a folder.
"""
import os
import logging
import voluptuous as vol
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['watchdog']
_LOGGER = logging.getLogger(__name__)

CONF_FOLDERS = 'folders'
DOMAIN = "folder_watcher"
DEFAULT_IS_RECURSIVE = True
EVENT_TYPE = "event_type"
IS_DIRECTORY = "is_directory"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_FOLDERS):
            vol.All(cv.ensure_list, [cv.isdir]),
        })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the folder watcher."""
    conf = config[DOMAIN]
    paths = conf[CONF_FOLDERS]
    for path in paths:
        if not hass.config.is_allowed_path(path):
            _LOGGER.error("folder %s is not valid or allowed", path)
            return False
        else:
            Watcher(path, hass)
    return True


class Watcher(Entity):
    """Class for starting Watchdog."""
    def __init__(self, path, hass):
        self._observer = Observer()
        self._observer.schedule(
            MyHandler(hass),
            path,
            recursive=DEFAULT_IS_RECURSIVE)
        self._observer.start()


def on_any_event(hass, event):
    if not event.is_directory:
        event_folder = os.path.split(event.src_path)[0]
        event_file = os.path.split(event.src_path)[1]
        hass.bus.fire(
                DOMAIN, {
                    EVENT_TYPE: event.event_type,
                    'file': event_file,
                    'folder': event_folder})


class MyHandler(FileSystemEventHandler):

    def __init__(self, hass):
        super().__init__()
        self.hass = hass

    def process(self, event):
        """Process the Watchdog event."""
        on_any_event(self.hass, event)

    def on_modified(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

    def on_deleted(self, event):
        self.process(event)
