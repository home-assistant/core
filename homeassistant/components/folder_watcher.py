"""
Component for monitoring activity on a folder.
"""
import asyncio
import logging
import voluptuous as vol
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

#DEPENDENCIES = ['watchdog']
_LOGGER = logging.getLogger(__name__)

CONF_PATH = 'folder'
DOMAIN = "watchdog_file_watcher"
EVENT_TYPE = "event_type"
SRC_PATH = "src_path"
PATTERNS = ["*.txt", "*.py", "*.md", "*.jpg", "*.png"]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PATH): cv.isdir})
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the folder watcher."""
    conf = config.get(DOMAIN)
    path = conf.get(CONF_PATH)
    if not hass.config.is_allowed_path(path):
        _LOGGER.error("folder %s is not valid or allowed", path)
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
            DOMAIN, {
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
