"""Support for file notification."""

from __future__ import annotations

import os
from typing import Any, TextIO

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

CONF_TIMESTAMP = "timestamp"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILENAME): cv.string,
        vol.Optional(CONF_TIMESTAMP, default=False): cv.boolean,
    }
)


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
