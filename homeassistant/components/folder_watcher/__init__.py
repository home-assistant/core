"""Component for monitoring activity on a folder."""
from __future__ import annotations

import logging
import os
from typing import cast

import voluptuous as vol
from watchdog.events import (
    FileClosedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemMovedEvent,
    PatternMatchingEventHandler,
)
from watchdog.observers import Observer

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_FOLDER = "folder"
CONF_PATTERNS = "patterns"
DEFAULT_PATTERN = "*"
DOMAIN = "folder_watcher"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_FOLDER): cv.isdir,
                        vol.Optional(CONF_PATTERNS, default=[DEFAULT_PATTERN]): vol.All(
                            cv.ensure_list, [cv.string]
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the folder watcher."""
    conf = config[DOMAIN]
    for watcher in conf:
        path: str = watcher[CONF_FOLDER]
        patterns: list[str] = watcher[CONF_PATTERNS]
        if not hass.config.is_allowed_path(path):
            _LOGGER.error("Folder %s is not valid or allowed", path)
            return False
        Watcher(path, patterns, hass)

    return True


def create_event_handler(patterns: list[str], hass: HomeAssistant) -> EventHandler:
    """Return the Watchdog EventHandler object."""

    return EventHandler(patterns, hass)


class EventHandler(PatternMatchingEventHandler):
    """Class for handling Watcher events."""

    def __init__(self, patterns: list[str], hass: HomeAssistant) -> None:
        """Initialise the EventHandler."""
        super().__init__(patterns)
        self.hass = hass

    def process(self, event: FileSystemEvent, moved: bool = False) -> None:
        """On Watcher event, fire HA event."""
        _LOGGER.debug("process(%s)", event)
        if not event.is_directory:
            folder, file_name = os.path.split(event.src_path)
            fireable = {
                "event_type": event.event_type,
                "path": event.src_path,
                "file": file_name,
                "folder": folder,
            }

            if moved:
                event = cast(FileSystemMovedEvent, event)
                dest_folder, dest_file_name = os.path.split(event.dest_path)
                fireable.update(
                    {
                        "dest_path": event.dest_path,
                        "dest_file": dest_file_name,
                        "dest_folder": dest_folder,
                    }
                )
            self.hass.bus.fire(
                DOMAIN,
                fireable,
            )

    def on_modified(self, event: FileModifiedEvent) -> None:
        """File modified."""
        self.process(event)

    def on_moved(self, event: FileMovedEvent) -> None:
        """File moved."""
        self.process(event, moved=True)

    def on_created(self, event: FileCreatedEvent) -> None:
        """File created."""
        self.process(event)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """File deleted."""
        self.process(event)

    def on_closed(self, event: FileClosedEvent) -> None:
        """File closed."""
        self.process(event)


class Watcher:
    """Class for starting Watchdog."""

    def __init__(self, path: str, patterns: list[str], hass: HomeAssistant) -> None:
        """Initialise the watchdog observer."""
        self._observer = Observer()
        self._observer.schedule(
            create_event_handler(patterns, hass), path, recursive=True
        )
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self.startup)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)

    def startup(self, event: Event) -> None:
        """Start the watcher."""
        self._observer.start()

    def shutdown(self, event: Event) -> None:
        """Shutdown the watcher."""
        self._observer.stop()
        self._observer.join()
