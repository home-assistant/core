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
COMPONENT_NAME = "watchdog_file_changed"
EVENT_TYPE = "event_type"
SRC_PATH = "src_path"
PATTERNS = ["*.txt", "*.py", "*.md", "*.jpg", "*.png"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PATH): cv.isdir,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the folder watcher."""
    path = config.get(CONF_PATH)
    if not hass.config.is_allowed_path(path):
        _LOGGER.error("folder %s is not valid or allowed", path)
    else:
        watcher = Watcher(path, hass)
        add_devices([watcher], True)


class Watcher(Entity):
    """Class for starting Watchdog."""
    def __init__(self, path, hass):
        self._observer = Observer()
        self._observer.schedule(
            MyHandler(hass),
            path,
            recursive=True)
        self._observer.start()


class MyHandler(PatternMatchingEventHandler):
    patterns = PATTERNS

    def __init__(self, hass):
        super().__init__()
        self.hass = hass

    def process(self, event):
        """Process the Watchdog event."""
        self.hass.bus.fire(
            COMPONENT_NAME, {
                EVENT_TYPE: event.event_type,
                SRC_PATH: event.src_path})

    def on_modified(self, event):
        self.process(event)

    def on_moved(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)

    def on_deleted(self, event):
        self.process(event)
