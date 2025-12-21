"""Support for file notification."""

from __future__ import annotations

import os
from typing import Any, TextIO

from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_TIMESTAMP, DEFAULT_NAME, DOMAIN, FILE_ICON


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up notify entity."""
    unique_id = entry.entry_id
    async_add_entities([FileNotifyEntity(unique_id, {**entry.data, **entry.options})])


class FileNotifyEntity(NotifyEntity):
    """Implement the notification entity platform for the File service."""

    _attr_icon = FILE_ICON
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, unique_id: str, config: dict[str, Any]) -> None:
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
