"""
Component for monitoring activity on a folder.

For more details about this platform, refer to the documentation at
https://home-assistant.io/components/folder_watcher/
"""
import os
import logging
import voluptuous as vol
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['watchdog==0.8.3']
_LOGGER = logging.getLogger(__name__)

CONF_FOLDER = 'folder'
CONF_PATTERNS = 'patterns'
CONF_WATCHERS = 'watchers'
DEFAULT_PATTERN = '*'
DOMAIN = "folder_watcher"
EVENT_TYPE = "event_type"
FILE = 'file'
FOLDER = 'folder'

WATCHER_CONFIG_SCHEMA = vol.Schema([{
    vol.Required(CONF_FOLDER): cv.isdir,
    vol.Optional(CONF_PATTERNS, default=[DEFAULT_PATTERN]): vol.All(
        cv.ensure_list, [cv.string]),
}])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: WATCHER_CONFIG_SCHEMA,
    }, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the folder watcher."""
    conf = config[DOMAIN]

    def run_setup(event):
        """"Wait for HA start then setup."""
        for watcher in conf:
            path = watcher[CONF_FOLDER]
            patterns = watcher[CONF_PATTERNS]
            if not hass.config.is_allowed_path(path):
                _LOGGER.error("folder %s is not valid or allowed", path)
                continue
            Watcher(path, patterns, hass)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, run_setup)
    return True


def create_event_handler(patterns, hass):
    """"Return the Watchdog EventHandler object."""
    from watchdog.events import PatternMatchingEventHandler

    class EventHandler(PatternMatchingEventHandler):
        """Class for handling Watcher events."""

        def __init__(self, patterns, hass):
            """Initialise the EventHandler."""
            super().__init__(patterns)
            self.hass = hass

        def process(self, event):
            """On Watcher event, fire HA event."""
            if not event.is_directory:
                folder_path, file_name = os.path.split(event.src_path)
                self.hass.bus.fire(
                    DOMAIN, {
                        EVENT_TYPE: event.event_type,
                        FILE: file_name,
                        FOLDER: folder_path
                        })

        def on_modified(self, event):
            """File modified."""
            self.process(event)

        def on_moved(self, event):
            """File moved."""
            self.process(event)

        def on_created(self, event):
            """File created."""
            self.process(event)

        def on_deleted(self, event):
            """File deleted."""
            self.process(event)

    return EventHandler(patterns, hass)


class Watcher(Entity):
    """Class for starting Watchdog."""

    def __init__(self, path, patterns, hass):
        """Initialise the Watchdog oberver."""
        from watchdog.observers import Observer
        self._observer = Observer()
        self._observer.schedule(
            create_event_handler(patterns, hass),
            path,
            recursive=True)
        self._observer.start()
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)

    def shutdown(self, event):
        """Shutdown the watcher."""
        self._observer.stop()
