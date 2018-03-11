"""
Component for monitoring activity on a folder.

For more details about this platform, refer to the documentation at
https://home-assistant.io/components/folder_watcher/
"""
import os
import logging
import voluptuous as vol
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

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_FOLDER): cv.isdir,
        vol.Optional(CONF_PATTERNS, default=[DEFAULT_PATTERN]):
            vol.All(cv.ensure_list, [cv.string]),
    })])
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the folder watcher."""
    conf = config[DOMAIN]
    for watcher in conf:
        path = watcher[CONF_FOLDER]
        patterns = watcher[CONF_PATTERNS]
        if not hass.config.is_allowed_path(path):
            _LOGGER.error("folder %s is not valid or allowed", path)
            continue
        Watcher(path, patterns, hass)

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

        def on_any_event(self, event):
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
            self.on_any_event(event)

        def on_moved(self, event):
            """File moved."""
            self.on_any_event(event)

        def on_created(self, event):
            """File created."""
            self.on_any_event(event)

        def on_deleted(self, event):
            """File deleted."""
            self.on_any_event(event)

    return EventHandler(patterns, hass)


class Watcher():
    """Class for starting Watchdog."""

    def __init__(self, path, patterns, hass):
        """Initialise the Watchdog oberver."""
        from watchdog.observers import Observer
        self._observer = Observer()
        self._observer.schedule(
            create_event_handler(patterns, hass),
            path,
            recursive=True)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self.startup)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)

    def startup(self, event):
        """Start the watcher."""
        self._observer.start()

    def shutdown(self, event):
        """Shutdown the watcher."""
        self._observer.stop()
