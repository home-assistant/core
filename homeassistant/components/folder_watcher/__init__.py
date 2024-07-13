"""Component for monitoring activity on a folder."""

from __future__ import annotations

import logging
import os
from typing import Any, cast

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

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FOLDER, CONF_PATTERNS, DEFAULT_PATTERN, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the folder watcher."""
    if DOMAIN in config:
        conf: list[dict[str, Any]] = config[DOMAIN]
        for watcher in conf:
            path: str = watcher[CONF_FOLDER]
            if not hass.config.is_allowed_path(path):
                async_create_issue(
                    hass,
                    DOMAIN,
                    f"import_failed_not_allowed_path_{path}",
                    is_fixable=False,
                    is_persistent=False,
                    severity=IssueSeverity.ERROR,
                    translation_key="import_failed_not_allowed_path",
                    translation_placeholders={
                        "path": path,
                        "config_variable": "allowlist_external_dirs",
                    },
                )
                continue
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=watcher
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Folder watcher from a config entry."""

    path: str = entry.options[CONF_FOLDER]
    patterns: list[str] = entry.options[CONF_PATTERNS]
    if not hass.config.is_allowed_path(path):
        _LOGGER.error("Folder %s is not valid or allowed", path)
        async_create_issue(
            hass,
            DOMAIN,
            f"setup_not_allowed_path_{path}",
            is_fixable=False,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key="setup_not_allowed_path",
            translation_placeholders={
                "path": path,
                "config_variable": "allowlist_external_dirs",
            },
            learn_more_url="https://www.home-assistant.io/docs/configuration/basic/#allowlist_external_dirs",
        )
        return False
    await hass.async_add_executor_job(Watcher, path, patterns, hass, entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def create_event_handler(
    patterns: list[str], hass: HomeAssistant, entry_id: str
) -> EventHandler:
    """Return the Watchdog EventHandler object."""
    return EventHandler(patterns, hass, entry_id)


class EventHandler(PatternMatchingEventHandler):
    """Class for handling Watcher events."""

    def __init__(self, patterns: list[str], hass: HomeAssistant, entry_id: str) -> None:
        """Initialise the EventHandler."""
        super().__init__(patterns)
        self.hass = hass
        self.entry_id = entry_id

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

            _extra = {}
            if moved:
                event = cast(FileSystemMovedEvent, event)
                dest_folder, dest_file_name = os.path.split(event.dest_path)
                _extra = {
                    "dest_path": event.dest_path,
                    "dest_file": dest_file_name,
                    "dest_folder": dest_folder,
                }
                fireable.update(_extra)
            self.hass.bus.fire(
                DOMAIN,
                fireable,
            )
            signal = f"folder_watcher-{self.entry_id}"
            dispatcher_send(self.hass, signal, event.event_type, fireable)

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

    def __init__(
        self, path: str, patterns: list[str], hass: HomeAssistant, entry_id: str
    ) -> None:
        """Initialise the watchdog observer."""
        self._observer = Observer()
        self._observer.schedule(
            create_event_handler(patterns, hass, entry_id), path, recursive=True
        )
        if not hass.is_running:
            hass.bus.listen_once(EVENT_HOMEASSISTANT_START, self.startup)
        else:
            self.startup(None)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)

    def startup(self, event: Event | None) -> None:
        """Start the watcher."""
        self._observer.start()

    def shutdown(self, event: Event | None) -> None:
        """Shutdown the watcher."""
        self._observer.stop()
        self._observer.join()
