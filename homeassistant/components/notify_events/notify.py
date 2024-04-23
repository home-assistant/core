"""Notify.Events platform for notify component."""

from __future__ import annotations

import logging
import os.path

from notify_events import Message

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

ATTR_LEVEL = "level"
ATTR_PRIORITY = "priority"

ATTR_FILES = "files"
ATTR_IMAGES = "images"

ATTR_FILE_URL = "url"
ATTR_FILE_PATH = "path"
ATTR_FILE_CONTENT = "content"
ATTR_FILE_NAME = "name"
ATTR_FILE_MIME_TYPE = "mime_type"

ATTR_FILE_KIND_FILE = "file"
ATTR_FILE_KIND_IMAGE = "image"

ATTR_TOKEN = "token"

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> NotifyEventsNotificationService:
    """Get the Notify.Events notification service."""
    return NotifyEventsNotificationService(hass.data[DOMAIN][CONF_TOKEN])


class NotifyEventsNotificationService(BaseNotificationService):
    """Implement the notification service for Notify.Events."""

    def __init__(self, token):
        """Initialize the service."""
        self.token = token

    def file_exists(self, filename) -> bool:
        """Check if a file exists on disk and is in authorized path."""
        if not self.hass.config.is_allowed_path(filename):
            return False
        return os.path.isfile(filename)

    def attach_file(self, msg: Message, item: dict, kind: str = ATTR_FILE_KIND_FILE):
        """Append a file or image to message."""
        file_name = None
        mime_type = None

        if ATTR_FILE_NAME in item:
            file_name = item[ATTR_FILE_NAME]

        if ATTR_FILE_MIME_TYPE in item:
            mime_type = item[ATTR_FILE_MIME_TYPE]

        if ATTR_FILE_URL in item:
            if kind == ATTR_FILE_KIND_IMAGE:
                msg.add_image_from_url(item[ATTR_FILE_URL], file_name, mime_type)
            else:
                msg.add_file_from_url(item[ATTR_FILE_URL], file_name, mime_type)
        elif ATTR_FILE_CONTENT in item:
            if kind == ATTR_FILE_KIND_IMAGE:
                msg.add_image_from_content(
                    item[ATTR_FILE_CONTENT], file_name, mime_type
                )
            else:
                msg.add_file_from_content(item[ATTR_FILE_CONTENT], file_name, mime_type)
        elif ATTR_FILE_PATH in item:
            file_exists = self.file_exists(item[ATTR_FILE_PATH])

            if file_exists:
                if kind == ATTR_FILE_KIND_IMAGE:
                    msg.add_image(item[ATTR_FILE_PATH], file_name, mime_type)
                else:
                    msg.add_file(item[ATTR_FILE_PATH], file_name, mime_type)
            else:
                _LOGGER.error("File does not exist: %s", item[ATTR_FILE_PATH])

    def prepare_message(self, message, data) -> Message:
        """Prepare a message to send."""
        msg = Message(message)

        if ATTR_TITLE in data:
            msg.set_title(data[ATTR_TITLE])

        if ATTR_LEVEL in data:
            try:
                msg.set_level(data[ATTR_LEVEL])
            except ValueError as error:
                _LOGGER.warning("Setting level error: %s", error)

        if ATTR_PRIORITY in data:
            try:
                msg.set_priority(data[ATTR_PRIORITY])
            except ValueError as error:
                _LOGGER.warning("Setting priority error: %s", error)

        if ATTR_IMAGES in data:
            for image in data[ATTR_IMAGES]:
                self.attach_file(msg, image, ATTR_FILE_KIND_IMAGE)

        if ATTR_FILES in data:
            for file in data[ATTR_FILES]:
                self.attach_file(msg, file)

        return msg

    def send_message(self, message, **kwargs):
        """Send a message."""
        data = kwargs.get(ATTR_DATA) or {}
        token = data.get(ATTR_TOKEN, self.token)

        msg = self.prepare_message(message, data)

        msg.send(token)
