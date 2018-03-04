"""
Component for monitoring activity on a folder.
"""
import logging
import voluptuous as vol
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

#DEPENDENCIES = ['watchdog']
_LOGGER = logging.getLogger(__name__)

CONF_PATH = 'folder'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PATH): cv.isdir,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the folder watcher."""
    path = config.get(CONF_PATH)
    if not hass.config.is_allowed_path(path):
        _LOGGER.error("folder %s is not valid or allowed", path)
    else:
        watcher = Watcher(path)
        add_devices([watcher], True)


class Watcher(Entity):
    """Class for watching a filesystem."""

    def __init__(self, path):
        self._observer = Observer()
        self._observer.schedule(
            MyHandler(self.fire_event), path, recursive=True)
        self._observer.start()

    def fire_event(self, data):
        _LOGGER.warning("WATCHDOG {} {}".format(
            data["event_type"], data["src_path"]))


class MyHandler(PatternMatchingEventHandler):
    patterns = ["*.txt", "*.py", "*.md", "*.jpg", "*.png"]

    def __init__(self, fire_event):
        super().__init__()
        self.fire_event = fire_event

    def process(self, event):
        """Process the Watchdog event."""
        data = {
            "event_type": event.event_type,
            "src_path": event.src_path,
        }
        self.fire_event(data)

    def on_modified(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

    def on_deleted(self, event):
        self.process(event)
