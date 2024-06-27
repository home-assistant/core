"""Support for file notification."""

from __future__ import annotations

from functools import partial
import logging
import os
from types import MappingProxyType
from typing import Any, TextIO

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
    migrate_notify_issue,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, CONF_FILENAME, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import CONF_TIMESTAMP, DEFAULT_NAME, DOMAIN, FILE_ICON

_LOGGER = logging.getLogger(__name__)

# The legacy platform schema uses a filename, after import
# The full file path is stored in the config entry
PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILENAME): cv.string,
        vol.Optional(CONF_TIMESTAMP, default=False): cv.boolean,
    }
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> FileNotificationService | None:
    """Get the file notification service."""
    if discovery_info is None:
        # We only set up through discovery
        return None
    file_path: str = discovery_info[CONF_FILE_PATH]
    timestamp: bool = discovery_info[CONF_TIMESTAMP]

    return FileNotificationService(file_path, timestamp)


class FileNotificationService(BaseNotificationService):
    """Implement the notification service for the File service."""

    def __init__(self, file_path: str, add_timestamp: bool) -> None:
        """Initialize the service."""
        self._file_path = file_path
        self.add_timestamp = add_timestamp

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a file."""
        # The use of the legacy notify service was deprecated with HA Core 2024.6.0
        # and will be removed with HA Core 2024.12
        migrate_notify_issue(
            self.hass, DOMAIN, "File", "2024.12.0", service_name=self._service_name
        )
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, **kwargs)
        )

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a file."""
        file: TextIO
        filepath = self._file_path
        try:
            with open(filepath, "a", encoding="utf8") as file:
                if os.stat(filepath).st_size == 0:
                    title = (
                        f"{kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)} notifications (Log"
                        f" started: {dt_util.utcnow().isoformat()})\n{'-' * 80}\n"
                    )
                    file.write(title)

                if self.add_timestamp:
                    text = f"{dt_util.utcnow().isoformat()} {message}\n"
                else:
                    text = f"{message}\n"
                file.write(text)
        except OSError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="write_access_failed",
                translation_placeholders={"filename": filepath, "exc": f"{exc!r}"},
            ) from exc


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up notify entity."""
    unique_id = entry.entry_id
    async_add_entities([FileNotifyEntity(unique_id, entry.data)])


class FileNotifyEntity(NotifyEntity):
    """Implement the notification entity platform for the File service."""

    _attr_icon = FILE_ICON
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, unique_id: str, config: MappingProxyType[str, Any]) -> None:
        """Initialize the service."""
        self._file_path: str = config[CONF_FILE_PATH]
        self._add_timestamp: bool = config.get(CONF_TIMESTAMP, False)
        # Only import a name from an imported entity
        self._attr_name = config.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = unique_id

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to a file."""
        file: TextIO
        filepath = self._file_path
        try:
            with open(filepath, "a", encoding="utf8") as file:
                if os.stat(filepath).st_size == 0:
                    title = (
                        f"{title or ATTR_TITLE_DEFAULT} notifications (Log"
                        f" started: {dt_util.utcnow().isoformat()})\n{'-' * 80}\n"
                    )
                    file.write(title)

                if self._add_timestamp:
                    text = f"{dt_util.utcnow().isoformat()} {message}\n"
                else:
                    text = f"{message}\n"
                file.write(text)
        except OSError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="write_access_failed",
                translation_placeholders={"filename": filepath, "exc": f"{exc!r}"},
            ) from exc
