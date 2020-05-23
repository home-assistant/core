"""Notify.Events platform for notify component."""
import logging
import os.path

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN
from notify_events import Message

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

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_TOKEN): cv.string})


def get_service(hass, config, discovery_info=None):
    """Get the Notify.Events notification service."""
    token = config[CONF_TOKEN]
    return NotifyEventsNotificationService(hass, token)


class NotifyEventsNotificationService(BaseNotificationService):
    """Implement the notification service for Notify.Events."""

    def __init__(self, hass, token):
        """Initialize the service."""
        self.token = token
        self.hass = hass

    def file_exists(self, filename) -> bool:
        """Check if a file exists on disk and is in authorized path."""
        if not self.hass.config.is_allowed_path(filename):
            return False
        return os.path.isfile(filename)

    async def attach_file(
        self, msg: Message, item: dict, kind: str = ATTR_FILE_KIND_FILE
    ):
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
            file_exists = await self.hass.async_add_executor_job(
                self.file_exists, item[ATTR_FILE_PATH]
            )

            if file_exists:
                if kind == ATTR_FILE_KIND_IMAGE:
                    msg.add_image(item[ATTR_FILE_PATH], file_name, mime_type)
                else:
                    msg.add_file(item[ATTR_FILE_PATH], file_name, mime_type)
            else:
                _LOGGER.error("File does not exist: %s", item[ATTR_FILE_PATH])

    async def prepare_message(self, message, data) -> Message:
        """Prepare a message to send"""
        msg = Message(message)

        if ATTR_TITLE in data:
            msg.set_title(data[ATTR_TITLE])

        if ATTR_LEVEL in data:
            try:
                msg.set_level(data[ATTR_LEVEL])
            except Exception as error:
                _LOGGER.warning("Setting level error: %s", error)

        if ATTR_PRIORITY in data:
            try:
                msg.set_priority(data[ATTR_PRIORITY])
            except Exception as error:
                _LOGGER.warning("Setting priority error: %s", error)

        if ATTR_IMAGES in data:
            for image in data[ATTR_IMAGES]:
                await self.attach_file(msg, image, ATTR_FILE_KIND_IMAGE)

        if ATTR_FILES in data:
            for file in data[ATTR_FILES]:
                await self.attach_file(msg, file)

        return msg

    async def async_send_message(self, message, **kwargs):
        """Send a message."""
        data = kwargs.get(ATTR_DATA) or {}

        msg = await self.prepare_message(message, data)
        msg.send(self.token)
