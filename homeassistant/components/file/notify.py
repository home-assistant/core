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
)
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import CONF_TIMESTAMP, DOMAIN, URL_ALLOWLIST_EXT_DIRS

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
    filename: str = discovery_info[CONF_FILENAME]
    timestamp: bool = discovery_info.get(CONF_TIMESTAMP, False)

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
        if not self.hass.config.is_allowed_path(filepath):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="dir_not_allowed",
                translation_placeholders={
                    "filename": filepath,
                    "url": URL_ALLOWLIST_EXT_DIRS,
                },
            )
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
        except Exception as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="write_access_failed",
                translation_placeholders={"filename": filepath, "exc": f"{exc!r}"},
            ) from exc
