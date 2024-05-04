"""Support for file notification."""

from __future__ import annotations

import logging
import os
from typing import Any, TextIO

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import FILE_ICON

_LOGGER = logging.getLogger(__name__)

CONF_TIMESTAMP = "timestamp"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILENAME): cv.string,
        vol.Optional(CONF_TIMESTAMP, default=False): cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the file sensor."""
    config: dict[str, Any] = dict(entry.data)
    if not await hass.async_add_executor_job(
        hass.config.is_allowed_path, config[CONF_FILENAME]
    ):
        _LOGGER.error("'%s' is not an allowed directory", config[CONF_FILENAME])
        return
    async_add_entities([FileNotifyEntity(config)])


class FileNotifyEntity(NotifyEntity):
    """Implement the notification entity platform for the File service."""

    _attr_icon = FILE_ICON
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the service."""
        self.filename: str = config[CONF_FILENAME]
        self.add_timestamp: bool = config.get(CONF_TIMESTAMP, False)
        self._attr_name = config.get(CONF_NAME, config[CONF_FILENAME])
        self._attr_unique_id = f"notify_{config[CONF_FILENAME]}"

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to a file."""
        file: TextIO
        filepath: str = os.path.join(self.hass.config.config_dir, self.filename)
        with open(filepath, "a", encoding="utf8") as file:
            if os.stat(filepath).st_size == 0:
                title = (
                    f"{title or ATTR_TITLE_DEFAULT} notifications (Log"
                    f" started: {dt_util.utcnow().isoformat()})\n{'-' * 80}\n"
                )
                file.write(title)

            if self.add_timestamp:
                text = f"{dt_util.utcnow().isoformat()} {message}\n"
            else:
                text = f"{message}\n"
            file.write(text)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> FileNotificationService:
    """Get the file notification service."""
    filename: str = config[CONF_FILENAME]
    timestamp: bool = config[CONF_TIMESTAMP]

    return FileNotificationService(filename, timestamp)


class FileNotificationService(BaseNotificationService):
    """Implement the notification service for the File service."""

    def __init__(self, filename: str, add_timestamp: bool) -> None:
        """Initialize the service."""
        self.filename = filename
        self.add_timestamp = add_timestamp

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a file."""
        file: TextIO
        filepath: str = os.path.join(self.hass.config.config_dir, self.filename)
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
